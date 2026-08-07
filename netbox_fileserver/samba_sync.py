"""RPC-driven Samba observed-state synchronization.

The module deliberately separates three concerns:

* :func:`dispatch_collect_state` invokes the seeded ``netbox-rpc`` intent;
* :func:`await_executions` performs a bounded terminal-state poll; and
* :func:`fold_result` is a side-effect-free handler-result to model-instance
  adapter which can be tested with lightweight model doubles.

Only successful procedure results are eligible for persistence.  Collection
replacement is additionally gated by the procedure which owns that collection,
so a failed or timed-out child never blanks last-known-good state.
"""

from __future__ import annotations

import ipaddress
import re
import shlex
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256

from netbox_rpc.constants import (
    FILESERVER_SAMBA_COLLECT_STATE,
    SAMBA_1_CONFIG_READ,
    SAMBA_1_CONFIG_TEST,
    SAMBA_1_DOMAIN_INFO,
    SAMBA_1_GROUP_LIST,
    SAMBA_1_LIST_SHARES,
    SAMBA_1_SERVICE_STATUS,
    SAMBA_1_STATUS_REPORT,
    SAMBA_1_USER_LIST,
    SAMBA_1_VERSION,
)

RPC_TERMINAL_STATUSES = frozenset(
    {"succeeded", "failed", "cancelled", "rejected", "expired"}
)
SAMBA_COLLECT_PROCEDURES = (
    SAMBA_1_VERSION,
    SAMBA_1_SERVICE_STATUS,
    SAMBA_1_CONFIG_READ,
    SAMBA_1_CONFIG_TEST,
    SAMBA_1_LIST_SHARES,
    SAMBA_1_STATUS_REPORT,
    SAMBA_1_USER_LIST,
    SAMBA_1_GROUP_LIST,
    SAMBA_1_DOMAIN_INFO,
)
SERVER_STATE_PROCEDURES = frozenset(
    {
        SAMBA_1_VERSION,
        SAMBA_1_SERVICE_STATUS,
        SAMBA_1_CONFIG_READ,
        SAMBA_1_CONFIG_TEST,
    }
)
SHARE_STATE_PROCEDURES = frozenset({SAMBA_1_CONFIG_TEST, SAMBA_1_LIST_SHARES})

DRIFT_IN_SYNC = "in_sync"
DRIFT_DRIFTED = "drifted"
DRIFT_MISSING = "missing_on_host"
DRIFT_UNMANAGED = "unmanaged"

_FOLD_FIELD_MARKER = "_samba_fold_fields"
_REDACTED = "[REDACTED]"
_UNSAFE_CONTENT_REDACTION = "[REDACTED: unsafe Samba configuration content]"
_PRIVATE_KEY_BEGIN_RE = re.compile(
    r"-{4,5}\s*BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?\s*-{4,5}", re.IGNORECASE
)
_PRIVATE_KEY_END_RE = re.compile(
    r"-{4,5}\s*END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?\s*-{4,5}", re.IGNORECASE
)
_PUTTY_PRIVATE_KEY_RE = re.compile(
    r"^PuTTY-User-Key-File-\d+:", re.IGNORECASE | re.MULTILINE
)
_FALLBACK_SECRET_NAME_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:authorization|cookie|credentials?|hash(?:es)?|keytabs?|"
    r"pass(?:code|phrase|w(?:or)?d|word)?s?|private[ _.-]*keys?|pwd|secrets?|"
    r"tokens?)(?:[^a-z0-9]|$)",
    re.IGNORECASE,
)

_MODEL_NAMES = (
    "SambaServerState",
    "SambaConfigFile",
    "SambaConfigSnapshot",
    "SambaObservedShare",
    "SambaObservedUser",
    "SambaObservedGroup",
    "SambaSession",
)


class SambaSyncIncomplete(RuntimeError):
    """The sync run reached a durable failed/partial terminal state."""


class SambaIntentDispatchError(RuntimeError):
    """Intent dispatch failed after zero or more children were committed."""

    def __init__(self, message: str, executions: Sequence[object]) -> None:
        super().__init__(message)
        self.executions = list(executions)


def _runtime_model_module():
    from . import models

    return models


def _runtime_model_classes() -> dict[str, type]:
    models = _runtime_model_module()
    return {name: getattr(models, name) for name in _MODEL_NAMES}


def _make_model(
    model_classes: Mapping[str, type], model_name: str, **fields: object
) -> object:
    instance = model_classes[model_name](**fields)
    setattr(instance, _FOLD_FIELD_MARKER, frozenset(fields))
    return instance


def _fallback_sensitive_name(value: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()
    compact = normalized.replace(" ", "")
    if compact.endswith(("password", "passwords", "passwd", "secret", "token")):
        return True
    return bool(_FALLBACK_SECRET_NAME_RE.search(normalized))


def _assignment_parts(line: str) -> tuple[str, str] | None:
    candidates = [(line.find(separator), separator) for separator in ("=", ":")]
    candidates = [(position, separator) for position, separator in candidates if position >= 0]
    if not candidates:
        return None
    position, separator = min(candidates)
    return line[:position], separator


def redact_secret_material(
    content: object,
    *,
    validator: Callable[..., None] | None = None,
    sensitive_name: Callable[[object], bool] | None = None,
) -> str:
    """Redact unsafe config lines and private-key blocks before persistence.

    In a NetBox runtime the observed-state model validator is used line by line
    and once more against the complete redacted value.  If the complete value
    still fails closed, the entire body is replaced with a safe marker instead
    of allowing ``ValidationError`` to escape into the sync job.
    """

    text = str(content or "")
    if _PUTTY_PRIVATE_KEY_RE.search(text):
        return _UNSAFE_CONTENT_REDACTION
    name_is_sensitive = sensitive_name or _fallback_sensitive_name
    trailing_newline = text.endswith(("\n", "\r"))
    redacted_lines: list[str] = []
    in_private_key = False

    for line in text.splitlines():
        if _PRIVATE_KEY_BEGIN_RE.search(line):
            in_private_key = True
            redacted_lines.append(_REDACTED)
            if _PRIVATE_KEY_END_RE.search(line):
                in_private_key = False
            continue
        if in_private_key:
            if _PRIVATE_KEY_END_RE.search(line):
                in_private_key = False
            continue

        assignment = _assignment_parts(line)
        unsafe = bool(assignment and name_is_sensitive(assignment[0]))
        if not unsafe and validator is not None:
            try:
                validator(line, field_name="content")
            except Exception:
                unsafe = True

        if unsafe:
            indentation = line[: len(line) - len(line.lstrip())]
            if assignment is None:
                redacted_lines.append(f"{indentation}{_REDACTED}")
            else:
                key, separator = assignment
                redacted_lines.append(
                    f"{indentation}{key.strip()} {separator} {_REDACTED}"
                )
        else:
            redacted_lines.append(line)

    redacted = "\n".join(redacted_lines)
    if trailing_newline and redacted:
        redacted += "\n"
    if validator is not None:
        try:
            validator(redacted, field_name="content")
        except Exception:
            return _UNSAFE_CONTENT_REDACTION
    return redacted


def _safe_mapping(
    values: Mapping[str, object],
    *,
    validator: Callable[..., None] | None,
    sensitive_name: Callable[[object], bool],
) -> dict[str, object]:
    sanitized = {
        str(key): _REDACTED if sensitive_name(key) else value
        for key, value in values.items()
    }
    if validator is not None:
        try:
            validator(sanitized, field_name="raw_params")
        except Exception:
            return {}
    return sanitized


def _parse_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"1", "yes", "true", "on", "enabled"}:
        return True
    if normalized in {"0", "no", "false", "off", "disabled"}:
        return False
    return default


def _parse_testparm_sections(
    content: str,
    *,
    validator: Callable[..., None] | None,
    sensitive_name: Callable[[object], bool],
) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current_name = ""
    current_params: dict[str, object] = {}

    def append_current() -> None:
        if current_name and current_name.casefold() != "global":
            sections.append(
                {
                    "name": current_name,
                    "params": _safe_mapping(
                        current_params,
                        validator=validator,
                        sensitive_name=sensitive_name,
                    ),
                }
            )

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            append_current()
            current_name = stripped[1:-1].strip()
            current_params = {}
            continue
        if not current_name or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = " ".join(key.strip().casefold().split())
        current_params[normalized_key] = (
            _REDACTED if sensitive_name(key) else value.strip()
        )
    append_current()
    return sections


def _share_models_from_config(
    content: str,
    *,
    model_classes: Mapping[str, type],
    validator: Callable[..., None] | None,
    sensitive_name: Callable[[object], bool],
) -> list[object]:
    instances = []
    for section in _parse_testparm_sections(
        content,
        validator=validator,
        sensitive_name=sensitive_name,
    ):
        params = section["params"]
        assert isinstance(params, dict)
        instances.append(
            _make_model(
                model_classes,
                "SambaObservedShare",
                name=section["name"],
                path=str(params.get("path") or ""),
                raw_params=params,
                browseable=_parse_bool(
                    params.get("browseable", params.get("browsable")),
                    default=True,
                ),
                read_only=_parse_bool(params.get("read only"), default=True),
                guest_ok=_parse_bool(params.get("guest ok"), default=False),
                drift_state=DRIFT_UNMANAGED,
            )
        )
    return instances


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if text.isdigit():
        return _parse_datetime(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _remote_ip(value: object) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    candidate = re.sub(r"^(?:ipv4|ipv6):", "", candidate, flags=re.IGNORECASE)
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.split(":", 1)[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _server_pid(value: Mapping[str, object]) -> int | None:
    server_id = value.get("server_id")
    nested_pid = server_id.get("pid") if isinstance(server_id, Mapping) else None
    return _positive_int(nested_pid or value.get("pid") or value.get("session_id"))


def _session_key(value: Mapping[str, object]) -> str:
    session_id = value.get("session_id")
    if session_id not in (None, ""):
        return str(session_id)
    pid = _server_pid(value)
    return str(pid or "")


def _session_models(
    result: Mapping[str, object], model_classes: Mapping[str, type]
) -> list[object]:
    raw_sessions = result.get("sessions")
    raw_tcons = result.get("tcons")
    sessions = (
        [item for item in raw_sessions if isinstance(item, dict)]
        if isinstance(raw_sessions, list)
        else []
    )
    tcons = (
        [item for item in raw_tcons if isinstance(item, dict)]
        if isinstance(raw_tcons, list)
        else []
    )
    tcons_by_session: dict[str, list[dict]] = {}
    for tcon in tcons:
        session_key = _session_key(tcon)
        if session_key:
            tcons_by_session.setdefault(session_key, []).append(tcon)

    instances: list[object] = []
    matched_sessions: set[str] = set()
    for session in sessions:
        pid = _server_pid(session)
        if pid is None:
            continue
        session_key = _session_key(session)
        matched_sessions.add(session_key)
        connections = tcons_by_session.get(session_key) or [{}]
        for connection in connections:
            remote = session.get("remote_machine") or session.get("remote_address")
            machine = (
                session.get("hostname")
                or session.get("machine")
                or session.get("remote_machine")
                or connection.get("machine")
                or ""
            )
            instances.append(
                _make_model(
                    model_classes,
                    "SambaSession",
                    username=str(session.get("username") or session.get("user") or ""),
                    machine=str(machine),
                    remote_ip=_remote_ip(remote),
                    share=str(
                        connection.get("service")
                        or connection.get("share")
                        or session.get("service")
                        or ""
                    ),
                    pid=pid,
                    opened_at=_parse_datetime(
                        session.get("creation_time")
                        or session.get("connect_time")
                        or session.get("opened_at")
                        or session.get("start_time")
                    ),
                )
            )
    for session_key, connections in tcons_by_session.items():
        if session_key in matched_sessions:
            continue
        for connection in connections:
            pid = _server_pid(connection)
            if pid is None:
                continue
            instances.append(
                _make_model(
                    model_classes,
                    "SambaSession",
                    username=str(connection.get("username") or ""),
                    machine=str(connection.get("machine") or ""),
                    remote_ip=_remote_ip(connection.get("machine")),
                    share=str(connection.get("service") or connection.get("share") or ""),
                    pid=pid,
                    opened_at=_parse_datetime(
                        connection.get("connected_at") or connection.get("connect_time")
                    ),
                )
            )
    return instances


def fold_result(
    procedure_name: str,
    result: Mapping[str, object],
    *,
    model_classes: Mapping[str, type] | None = None,
) -> list[object]:
    """Convert one successful dotted RPC procedure result to unsaved models.

    The function performs no database or network I/O.  ``model_classes`` is an
    optional test seam; production callers omit it and receive real Django
    model instances.
    """

    if not isinstance(result, Mapping):
        raise ValueError("RPC result must be a mapping.")
    runtime_models = None
    if model_classes is None:
        runtime_models = _runtime_model_module()
        model_classes = _runtime_model_classes()
    validator = getattr(runtime_models, "validate_no_secret_material", None)
    sensitive_name = getattr(runtime_models, "_is_sensitive_name", _fallback_sensitive_name)

    if procedure_name == SAMBA_1_VERSION:
        return [
            _make_model(
                model_classes,
                "SambaServerState",
                version=str(result.get("version") or ""),
            )
        ]

    if procedure_name == SAMBA_1_SERVICE_STATUS:
        fields: dict[str, object] = {}
        services = result.get("services")
        if isinstance(services, list):
            unit_prefixes = {
                "smbd.service": "smbd",
                "nmbd.service": "nmbd",
                "winbind.service": "winbind",
                "samba-ad-dc.service": "samba_ad_dc",
            }
            for service in services:
                if not isinstance(service, Mapping):
                    continue
                prefix = unit_prefixes.get(str(service.get("unit") or "").casefold())
                if prefix is None:
                    continue
                for source, suffix in (
                    ("active_state", "active_state"),
                    ("sub_state", "sub_state"),
                    ("unit_file_state", "unit_file_state"),
                ):
                    fields[f"{prefix}_{suffix}"] = str(service.get(source) or "")
        return [_make_model(model_classes, "SambaServerState", **fields)]

    if procedure_name == SAMBA_1_CONFIG_READ:
        raw_content = str(result.get("content") or "")
        content = redact_secret_material(
            raw_content,
            validator=validator,
            sensitive_name=sensitive_name,
        )
        path = str(result.get("path") or "")
        digest = str(result.get("sha256") or "").lower()
        snapshot_id = digest or sha256(content.encode("utf-8")).hexdigest()
        instances = [
            _make_model(
                model_classes,
                "SambaConfigFile",
                path=path,
                content=content,
                sha256=digest,
                size=len(raw_content.encode("utf-8")),
                mtime=None,
                is_primary=True,
                fetched_at=None,
            ),
            _make_model(
                model_classes,
                "SambaConfigSnapshot",
                snapshot_id=snapshot_id,
                content={
                    "files": {
                        path: {
                            "content": content,
                            "sha256": digest,
                            "size": len(raw_content.encode("utf-8")),
                        }
                    }
                },
            ),
            _make_model(
                model_classes,
                "SambaServerState",
                config_sha256=digest,
            ),
        ]
        instances.extend(
            _share_models_from_config(
                content,
                model_classes=model_classes,
                validator=validator,
                sensitive_name=sensitive_name,
            )
        )
        return instances

    if procedure_name == SAMBA_1_CONFIG_TEST:
        stdout = redact_secret_material(
            result.get("stdout"),
            validator=validator,
            sensitive_name=sensitive_name,
        )
        instances = [
            _make_model(
                model_classes,
                "SambaServerState",
                testparm_ok=bool(result.get("valid")),
            )
        ]
        instances.extend(
            _share_models_from_config(
                stdout,
                model_classes=model_classes,
                validator=validator,
                sensitive_name=sensitive_name,
            )
        )
        return instances

    if procedure_name == SAMBA_1_LIST_SHARES:
        shares = result.get("shares")
        if not isinstance(shares, list):
            return []
        return [
            _make_model(
                model_classes,
                "SambaObservedShare",
                name=str(share.get("name") or ""),
                path="",
                raw_params={},
                browseable=True,
                read_only=True,
                guest_ok=False,
                drift_state=DRIFT_UNMANAGED,
            )
            for share in shares
            if isinstance(share, Mapping) and share.get("name")
        ]

    if procedure_name == SAMBA_1_STATUS_REPORT:
        return _session_models(result, model_classes)

    if procedure_name == SAMBA_1_USER_LIST:
        users = result.get("users")
        if not isinstance(users, list):
            return []
        return [
            _make_model(
                model_classes,
                "SambaObservedUser",
                username=str(user.get("username") or ""),
                sid="",
                enabled=True,
                last_logon=None,
            )
            for user in users
            if isinstance(user, Mapping) and user.get("username")
        ]

    if procedure_name == SAMBA_1_GROUP_LIST:
        groups = result.get("groups")
        if not isinstance(groups, list):
            return []
        return [
            _make_model(
                model_classes,
                "SambaObservedGroup",
                name=str(group.get("name") or ""),
                sid="",
                members=[str(member) for member in group.get("members", [])],
            )
            for group in groups
            if isinstance(group, Mapping)
            and group.get("name")
            and isinstance(group.get("members", []), list)
        ]

    if procedure_name == SAMBA_1_DOMAIN_INFO:
        # #15 intentionally added no observed domain-metadata columns.  Keep an
        # explicit fold branch so the known procedure is accepted, while never
        # overwriting desired SambaDomain.realm/netbios/functional_level fields.
        return []

    raise ValueError(f"Unsupported Samba RPC procedure {procedure_name!r}.")


def _object_value(instance: object, name: str, default: object = None) -> object:
    if isinstance(instance, Mapping):
        return instance.get(name, default)
    return getattr(instance, name, default)


def _split_acl_subjects(value: object) -> list[str]:
    subjects = []
    try:
        tokens = shlex.split(str(value or "").replace(",", " "))
    except ValueError:
        tokens = re.split(r"[\s,]+", str(value or "").strip())
    for token in tokens:
        subject = token.strip("'\"@")
        if "\\" in subject:
            subject = subject.rsplit("\\", 1)[-1]
        if subject:
            subjects.append(subject)
    return subjects


def _derived_acl_spec(raw_params: Mapping[str, object], *, read_only: bool) -> list[dict]:
    explicit = raw_params.get("acl_spec")
    if isinstance(explicit, list):
        return [dict(entry) for entry in explicit if isinstance(entry, Mapping)]

    roles: dict[str, str] = {}
    for key, role in (
        ("valid users", "ro" if read_only else "rw"),
        ("read list", "ro"),
        ("write list", "rw"),
        ("admin users", "full"),
        ("invalid users", "deny"),
    ):
        for group in _split_acl_subjects(raw_params.get(key)):
            roles[group] = role
    return [{"group": group, "role": role} for group, role in roles.items()]


def _normalized_acl(value: object) -> tuple[tuple[str, str], ...] | None:
    if not isinstance(value, list):
        return None
    normalized = []
    for entry in value:
        if not isinstance(entry, Mapping):
            return None
        group = str(entry.get("group") or "").strip().casefold()
        role = str(entry.get("role") or "").strip().casefold()
        if not group or not role:
            return None
        normalized.append((group, role))
    return tuple(sorted(normalized))


def _observed_vfs_flag(raw_params: Mapping[str, object], explicit: str, module: str) -> bool:
    if explicit in raw_params:
        return _parse_bool(raw_params[explicit], default=False)
    modules = {
        item.casefold().removeprefix("vfs_")
        for item in str(raw_params.get("vfs objects") or "").split()
    }
    return module.casefold().removeprefix("vfs_") in modules


def compute_drift_state(desired: object | None, observed: object | None) -> str:
    """Compute the four-state desired/observed share comparison."""

    if desired is None:
        return DRIFT_UNMANAGED
    if observed is None:
        return DRIFT_MISSING
    raw_params = _object_value(observed, "raw_params", {})
    if not isinstance(raw_params, Mapping):
        raw_params = {}
    if raw_params.get("_missing_on_host") is True:
        return DRIFT_MISSING

    read_only = bool(_object_value(observed, "read_only", True))
    desired_values = (
        str(_object_value(desired, "name", "")),
        str(_object_value(desired, "path", "")),
        bool(_object_value(desired, "smb_enabled", True)),
        _normalized_acl(_object_value(desired, "acl_spec", [])),
        bool(_object_value(desired, "snapshots_enabled", False)),
        bool(_object_value(desired, "recycle_enabled", False)),
    )
    observed_values = (
        str(_object_value(observed, "name", "")),
        str(_object_value(observed, "path", "")),
        _parse_bool(raw_params.get("smb_enabled"), default=True),
        _normalized_acl(_derived_acl_spec(raw_params, read_only=read_only)),
        _observed_vfs_flag(raw_params, "snapshots_enabled", "shadow_copy2"),
        _observed_vfs_flag(raw_params, "recycle_enabled", "recycle"),
    )
    return DRIFT_IN_SYNC if desired_values == observed_values else DRIFT_DRIFTED


def replacement_plan(procedure_statuses: Mapping[str, str]) -> dict[str, bool]:
    """Return which collections are safe to replace for a terminal sweep."""

    succeeded = {
        name for name, status in procedure_statuses.items() if status == "succeeded"
    }
    return {
        "server_state": succeeded >= SERVER_STATE_PROCEDURES,
        "config": SAMBA_1_CONFIG_READ in succeeded,
        "shares": succeeded >= SHARE_STATE_PROCEDURES,
        "sessions": SAMBA_1_STATUS_REPORT in succeeded,
        "users": SAMBA_1_USER_LIST in succeeded,
        "groups": SAMBA_1_GROUP_LIST in succeeded,
    }


def classify_sync_status(
    procedure_statuses: Mapping[str, str],
    *,
    has_dispatch_error: bool = False,
    has_fold_error: bool = False,
) -> str:
    """Classify a sweep as succeeded, partial, or failed."""

    statuses = [procedure_statuses.get(name, "missing") for name in SAMBA_COLLECT_PROCEDURES]
    succeeded = sum(status == "succeeded" for status in statuses)
    complete = succeeded == len(SAMBA_COLLECT_PROCEDURES)
    if complete and not has_dispatch_error and not has_fold_error:
        return "succeeded"
    return "partial" if succeeded else "failed"


def dispatch_collect_state(domain: object, user: object) -> list[object]:
    """Dispatch the seeded collect-state intent and recover partial fan-out IDs."""

    from django.contrib.contenttypes.models import ContentType
    from netbox_rpc.application.command_handlers import execute_intent
    from netbox_rpc.models import RPCExecution, RPCIntent

    assigned_type = ContentType.objects.get_for_model(domain, for_concrete_model=False)
    base_queryset = RPCExecution.objects.filter(
        assigned_object_type=assigned_type,
        assigned_object_id=domain.pk,
        requested_by=user,
        procedure__name__in=SAMBA_COLLECT_PROCEDURES,
    )
    existing_ids = set(base_queryset.values_list("pk", flat=True))
    try:
        intent = RPCIntent.objects.get(name=FILESERVER_SAMBA_COLLECT_STATE, enabled=True)
        return execute_intent(
            intent,
            user,
            assigned_object_type=assigned_type,
            assigned_object_id=domain.pk,
            params={},
        )
    except Exception as exc:
        committed = list(
            base_queryset.exclude(pk__in=existing_ids)
            .filter(params__contains={"_intent_name": FILESERVER_SAMBA_COLLECT_STATE})
            .select_related("procedure")
            .order_by("pk")
        )
        raise SambaIntentDispatchError(str(exc), committed) from None


def await_executions(
    execution_ids: Sequence[int],
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> tuple[list[object], set[int]]:
    """Poll executions to terminal state, returning timed-out/missing IDs."""

    from netbox_rpc.models import RPCExecution

    ids = tuple(dict.fromkeys(int(execution_id) for execution_id in execution_ids))
    deadline = time.monotonic() + max(timeout_seconds, 0)
    while True:
        executions = list(
            RPCExecution.objects.filter(pk__in=ids)
            .select_related("procedure")
            .order_by("pk")
        )
        by_id = {execution.pk: execution for execution in executions}
        pending = {
            execution_id
            for execution_id in ids
            if execution_id not in by_id
            or by_id[execution_id].status not in RPC_TERMINAL_STATUSES
        }
        if not pending:
            return executions, set()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return executions, pending
        time.sleep(min(max(poll_interval_seconds, 0.05), remaining))


def _fields_from_fold(instance: object) -> dict[str, object]:
    names = getattr(instance, _FOLD_FIELD_MARKER, ())
    return {name: getattr(instance, name) for name in names}


def _instances_named(instances: Sequence[object], class_name: str) -> list[object]:
    return [instance for instance in instances if type(instance).__name__ == class_name]


def _validate_instance(instance: object) -> None:
    instance.full_clean()


def _safe_error_text(value: object) -> str:
    models = _runtime_model_module()
    return redact_secret_material(
        str(value or ""),
        validator=models.validate_no_secret_material,
        sensitive_name=models._is_sensitive_name,
    )


def _persist_server_state(domain: object, folded: Mapping[str, Sequence[object]], observed_at) -> None:
    from django.db import transaction

    models = _runtime_model_module()
    defaults: dict[str, object] = {}
    for procedure_name in SAMBA_COLLECT_PROCEDURES:
        for instance in _instances_named(folded.get(procedure_name, ()), "SambaServerState"):
            defaults.update(_fields_from_fold(instance))
    defaults["observed_at"] = observed_at
    candidate = models.SambaServerState(domain=domain, **defaults)
    _validate_instance(candidate)
    with transaction.atomic():
        models.SambaServerState.objects.update_or_create(domain=domain, defaults=defaults)


def _persist_config(domain: object, instances: Sequence[object], observed_at) -> None:
    from django.db import transaction

    models = _runtime_model_module()
    config_files = _instances_named(instances, "SambaConfigFile")
    snapshots = _instances_named(instances, "SambaConfigSnapshot")
    with transaction.atomic():
        for instance in config_files:
            fields = _fields_from_fold(instance)
            fields["mtime"] = fields.get("mtime") or observed_at
            fields["fetched_at"] = fields.get("fetched_at") or observed_at
            path = fields.pop("path")
            candidate = models.SambaConfigFile(domain=domain, path=path, **fields)
            try:
                _validate_instance(candidate)
            except Exception:
                candidate.content = _UNSAFE_CONTENT_REDACTION
                fields["content"] = candidate.content
                _validate_instance(candidate)
            models.SambaConfigFile.objects.update_or_create(
                domain=domain,
                path=path,
                defaults=fields,
            )
        for instance in snapshots:
            fields = _fields_from_fold(instance)
            snapshot_id = fields.pop("snapshot_id")
            candidate = models.SambaConfigSnapshot(
                domain=domain,
                snapshot_id=snapshot_id,
                **fields,
            )
            try:
                _validate_instance(candidate)
            except Exception:
                candidate.content = {"redacted": _UNSAFE_CONTENT_REDACTION}
                fields["content"] = candidate.content
                _validate_instance(candidate)
            models.SambaConfigSnapshot.objects.update_or_create(
                domain=domain,
                snapshot_id=snapshot_id,
                defaults=fields,
            )


def _persist_shares(domain: object, folded: Mapping[str, Sequence[object]]) -> None:
    from django.db import transaction

    models = _runtime_model_module()
    desired_shares = list(models.FileShare.objects.filter(deployment=domain.deployment))
    desired_by_key = {share.name.casefold(): share for share in desired_shares}

    rich_by_key: dict[str, object] = {}
    for procedure_name in (SAMBA_1_CONFIG_READ, SAMBA_1_CONFIG_TEST):
        for instance in _instances_named(
            folded.get(procedure_name, ()), "SambaObservedShare"
        ):
            rich_by_key[str(instance.name).casefold()] = instance

    existing_by_key = {
        share.name.casefold(): share
        for share in models.SambaObservedShare.objects.filter(domain=domain)
    }

    authoritative = _instances_named(
        folded.get(SAMBA_1_LIST_SHARES, ()), "SambaObservedShare"
    )
    observed_keys: set[str] = set()
    keep_names: list[str] = []
    with transaction.atomic():
        for listed in authoritative:
            key = str(listed.name).casefold()
            observed_keys.add(key)
            rich = rich_by_key.get(key)
            if rich is not None:
                fields = _fields_from_fold(rich)
            else:
                previous = existing_by_key.get(key)
                if previous is not None:
                    # Authoritative list_shares confirmed the share still
                    # exists, but this sweep has no rich testparm/config_read
                    # entry for it. Keep the prior rich fields rather than
                    # blanking path/ACL data to the name-only defaults.
                    fields = {
                        "path": previous.path,
                        "raw_params": previous.raw_params,
                        "browseable": previous.browseable,
                        "read_only": previous.read_only,
                        "guest_ok": previous.guest_ok,
                    }
                else:
                    fields = _fields_from_fold(listed)
            fields["name"] = str(listed.name)
            fields["drift_state"] = compute_drift_state(
                desired_by_key.get(key),
                {**fields, "name": str(listed.name)},
            )
            name = str(fields.pop("name"))
            candidate = models.SambaObservedShare(domain=domain, name=name, **fields)
            _validate_instance(candidate)
            models.SambaObservedShare.objects.update_or_create(
                domain=domain,
                name=name,
                defaults=fields,
            )
            keep_names.append(name)

        for desired in desired_shares:
            if desired.name.casefold() in observed_keys:
                continue
            fields = {
                "path": "",
                "raw_params": {"_missing_on_host": True},
                "browseable": True,
                "read_only": True,
                "guest_ok": False,
                "drift_state": DRIFT_MISSING,
            }
            candidate = models.SambaObservedShare(
                domain=domain,
                name=desired.name,
                **fields,
            )
            _validate_instance(candidate)
            models.SambaObservedShare.objects.update_or_create(
                domain=domain,
                name=desired.name,
                defaults=fields,
            )
            keep_names.append(desired.name)

        models.SambaObservedShare.objects.filter(domain=domain).exclude(
            name__in=keep_names
        ).delete()


def _replace_keyed_collection(
    *,
    domain: object,
    instances: Sequence[object],
    class_name: str,
    key_field: str,
) -> None:
    from django.db import transaction

    models = _runtime_model_module()
    model_class = getattr(models, class_name)
    kept: list[str] = []
    with transaction.atomic():
        for instance in _instances_named(instances, class_name):
            fields = _fields_from_fold(instance)
            key = str(fields.pop(key_field))
            candidate = model_class(domain=domain, **{key_field: key}, **fields)
            _validate_instance(candidate)
            model_class.objects.update_or_create(
                domain=domain,
                **{key_field: key},
                defaults=fields,
            )
            kept.append(key)
        model_class.objects.filter(domain=domain).exclude(
            **{f"{key_field}__in": kept}
        ).delete()


def _replace_sessions(domain: object, instances: Sequence[object]) -> None:
    from django.db import transaction

    models = _runtime_model_module()
    candidates = []
    for instance in _instances_named(instances, "SambaSession"):
        candidate = models.SambaSession(domain=domain, **_fields_from_fold(instance))
        _validate_instance(candidate)
        candidates.append(candidate)
    with transaction.atomic():
        models.SambaSession.objects.filter(domain=domain).delete()
        models.SambaSession.objects.bulk_create(candidates)


def persist_successful_results(
    *,
    domain: object,
    executions: Sequence[object],
    procedure_statuses: Mapping[str, str],
    observed_at: object,
) -> dict[str, str]:
    """Fold and persist eligible results, returning sanitized per-stage errors."""

    folded: dict[str, list[object]] = {}
    errors: dict[str, str] = {}
    for execution in executions:
        procedure_name = execution.procedure.name
        if procedure_statuses.get(procedure_name) != "succeeded":
            continue
        try:
            folded[procedure_name] = fold_result(procedure_name, execution.result or {})
        except Exception as exc:
            errors[procedure_name] = _safe_error_text(str(exc))

    effective_statuses = dict(procedure_statuses)
    for procedure_name in errors:
        effective_statuses[procedure_name] = "fold_failed"
    plan = replacement_plan(effective_statuses)

    persistence_steps: list[tuple[str, Callable[[], None], set[str]]] = [
        (
            "server_state",
            lambda: _persist_server_state(domain, folded, observed_at),
            set(SERVER_STATE_PROCEDURES),
        ),
        (
            "config",
            lambda: _persist_config(
                domain,
                folded.get(SAMBA_1_CONFIG_READ, ()),
                observed_at,
            ),
            {SAMBA_1_CONFIG_READ},
        ),
        (
            "shares",
            lambda: _persist_shares(domain, folded),
            set(SHARE_STATE_PROCEDURES),
        ),
        (
            "sessions",
            lambda: _replace_sessions(
                domain,
                folded.get(SAMBA_1_STATUS_REPORT, ()),
            ),
            {SAMBA_1_STATUS_REPORT},
        ),
        (
            "users",
            lambda: _replace_keyed_collection(
                domain=domain,
                instances=folded.get(SAMBA_1_USER_LIST, ()),
                class_name="SambaObservedUser",
                key_field="username",
            ),
            {SAMBA_1_USER_LIST},
        ),
        (
            "groups",
            lambda: _replace_keyed_collection(
                domain=domain,
                instances=folded.get(SAMBA_1_GROUP_LIST, ()),
                class_name="SambaObservedGroup",
                key_field="name",
            ),
            {SAMBA_1_GROUP_LIST},
        ),
    ]
    for stage, callback, owners in persistence_steps:
        if not plan[stage]:
            continue
        try:
            callback()
        except Exception as exc:
            message = _safe_error_text(str(exc))
            for procedure_name in owners:
                errors.setdefault(procedure_name, f"{stage}: {message}")
    return errors


def _finish_sync_run(sync_run: object, *, status: str, errors: Sequence[str]) -> None:
    from django.utils import timezone

    sync_run.status = status
    sync_run.finished = timezone.now()
    sync_run.error_message = _safe_error_text("\n".join(error for error in errors if error))
    sync_run.full_clean()
    sync_run.save(update_fields=("status", "finished", "error_message", "last_updated"))


def perform_samba_sync(
    *,
    sync_run: object,
    domain: object,
    user: object,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    """Dispatch, await, fold, and persist one durable Samba sync run."""

    from django.utils import timezone

    dispatch_error = ""
    try:
        try:
            children = dispatch_collect_state(domain, user)
        except SambaIntentDispatchError as exc:
            children = exc.executions
            dispatch_error = _safe_error_text(str(exc))

        execution_ids = [int(execution.pk) for execution in children]
        sync_run.rpc_execution_ids = execution_ids
        sync_run.full_clean()
        sync_run.save(update_fields=("rpc_execution_ids", "last_updated"))

        executions, timed_out_ids = await_executions(
            execution_ids,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        ) if execution_ids else ([], set())
        by_procedure = {execution.procedure.name: execution for execution in executions}
        procedure_statuses: dict[str, str] = {}
        errors: list[str] = []
        if dispatch_error:
            errors.append(f"intent dispatch: {dispatch_error}")
        for procedure_name in SAMBA_COLLECT_PROCEDURES:
            execution = by_procedure.get(procedure_name)
            if execution is None:
                procedure_statuses[procedure_name] = "missing"
                errors.append(f"{procedure_name}: no RPC execution was created")
                continue
            if execution.pk in timed_out_ids:
                procedure_statuses[procedure_name] = "timed_out"
                errors.append(f"{procedure_name} #{execution.pk}: timed out")
                continue
            procedure_statuses[procedure_name] = execution.status
            if execution.status != "succeeded":
                detail = _safe_error_text(
                    execution.error_message or execution.error_code or execution.status
                )
                errors.append(f"{procedure_name} #{execution.pk}: {detail}")

        fold_errors = persist_successful_results(
            domain=domain,
            executions=executions,
            procedure_statuses=procedure_statuses,
            observed_at=timezone.now(),
        )
        errors.extend(
            f"{procedure_name}: {message}"
            for procedure_name, message in sorted(fold_errors.items())
        )
        status = classify_sync_status(
            procedure_statuses,
            has_dispatch_error=bool(dispatch_error),
            has_fold_error=bool(fold_errors),
        )
        _finish_sync_run(sync_run, status=status, errors=errors)
        if status != "succeeded":
            raise SambaSyncIncomplete(
                f"Samba sync run {sync_run.pk} completed with status {status}."
            )
    except SambaSyncIncomplete:
        raise
    except Exception as exc:
        _finish_sync_run(sync_run, status="failed", errors=[_safe_error_text(str(exc))])
        raise SambaSyncIncomplete(f"Samba sync run {sync_run.pk} failed.") from None
