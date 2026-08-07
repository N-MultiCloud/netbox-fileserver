"""Pure unit tests for the RPC Samba fold, redaction, and drift engine."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads(
    (ROOT / "tests" / "fixtures" / "samba_collect_state.json").read_text()
)

PROCEDURE_NAMES = {
    "FILESERVER_SAMBA_COLLECT_STATE": "fileserver.samba.collect_state",
    "SAMBA_1_VERSION": "service.samba.1.version",
    "SAMBA_1_SERVICE_STATUS": "service.samba.1.service_status",
    "SAMBA_1_CONFIG_READ": "service.samba.1.config_read",
    "SAMBA_1_CONFIG_TEST": "service.samba.1.config_test",
    "SAMBA_1_LIST_SHARES": "service.samba.1.list_shares",
    "SAMBA_1_STATUS_REPORT": "service.samba.1.status_report",
    "SAMBA_1_USER_LIST": "service.samba.1.user_list",
    "SAMBA_1_GROUP_LIST": "service.samba.1.group_list",
    "SAMBA_1_DOMAIN_INFO": "service.samba.1.domain_info",
}


def _load_sync_module():
    """Load the pure module with a tiny netbox-rpc constants test double."""

    rpc_package = types.ModuleType("netbox_rpc")
    constants = types.ModuleType("netbox_rpc.constants")
    for name, value in PROCEDURE_NAMES.items():
        setattr(constants, name, value)
    previous_package = sys.modules.get("netbox_rpc")
    previous_constants = sys.modules.get("netbox_rpc.constants")
    sys.modules["netbox_rpc"] = rpc_package
    sys.modules["netbox_rpc.constants"] = constants
    try:
        spec = importlib.util.spec_from_file_location(
            "netbox_fileserver_samba_sync_unit",
            ROOT / "netbox_fileserver" / "samba_sync.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_package is None:
            sys.modules.pop("netbox_rpc", None)
        else:
            sys.modules["netbox_rpc"] = previous_package
        if previous_constants is None:
            sys.modules.pop("netbox_rpc.constants", None)
        else:
            sys.modules["netbox_rpc.constants"] = previous_constants


SYNC = _load_sync_module()


class _ModelDouble:
    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


MODEL_CLASSES = {
    name: type(name, (_ModelDouble,), {})
    for name in (
        "SambaServerState",
        "SambaConfigFile",
        "SambaConfigSnapshot",
        "SambaObservedShare",
        "SambaObservedUser",
        "SambaObservedGroup",
        "SambaSession",
    )
}


@pytest.mark.parametrize(
    ("procedure_name", "expected_classes"),
    (
        ("service.samba.1.version", {"SambaServerState"}),
        ("service.samba.1.service_status", {"SambaServerState"}),
        (
            "service.samba.1.config_read",
            {
                "SambaConfigFile",
                "SambaConfigSnapshot",
                "SambaObservedShare",
                "SambaServerState",
            },
        ),
        (
            "service.samba.1.config_test",
            {"SambaObservedShare", "SambaServerState"},
        ),
        ("service.samba.1.list_shares", {"SambaObservedShare"}),
        ("service.samba.1.status_report", {"SambaSession"}),
        ("service.samba.1.user_list", {"SambaObservedUser"}),
        ("service.samba.1.group_list", {"SambaObservedGroup"}),
        ("service.samba.1.domain_info", set()),
    ),
)
def test_fold_result_fixture_per_collect_procedure(procedure_name, expected_classes):
    instances = SYNC.fold_result(
        procedure_name,
        FIXTURES[procedure_name],
        model_classes=MODEL_CLASSES,
    )
    assert {type(instance).__name__ for instance in instances} == expected_classes


def test_fold_maps_service_status_and_real_smbstatus_shape():
    [state] = SYNC.fold_result(
        "service.samba.1.service_status",
        FIXTURES["service.samba.1.service_status"],
        model_classes=MODEL_CLASSES,
    )
    assert state.smbd_active_state == "active"
    assert state.nmbd_sub_state == "dead"
    assert state.samba_ad_dc_unit_file_state == "enabled"

    [session] = SYNC.fold_result(
        "service.samba.1.status_report",
        FIXTURES["service.samba.1.status_report"],
        model_classes=MODEL_CLASSES,
    )
    assert session.pid == 4321
    assert session.username == "alice"
    assert session.machine == "LAPTOP-ALICE"
    assert session.remote_ip == "10.0.30.9"
    assert session.share == "Finance"
    assert session.opened_at.isoformat() == "2026-08-07T01:02:03+00:00"


def test_config_fold_redacts_secret_assignments_before_file_and_snapshot():
    instances = SYNC.fold_result(
        "service.samba.1.config_read",
        FIXTURES["service.samba.1.config_read"],
        model_classes=MODEL_CLASSES,
    )
    config_file = next(
        instance for instance in instances if type(instance).__name__ == "SambaConfigFile"
    )
    snapshot = next(
        instance
        for instance in instances
        if type(instance).__name__ == "SambaConfigSnapshot"
    )
    assert "encrypt passwords = yes" not in config_file.content
    assert "encrypt passwords = [REDACTED]" in config_file.content
    assert "workgroup = EXAMPLE" in config_file.content
    serialized_snapshot = json.dumps(snapshot.content)
    assert "encrypt passwords = yes" not in serialized_snapshot
    assert "[REDACTED]" in serialized_snapshot


def test_redaction_scrubs_validator_rejections_and_private_key_blocks():
    def validator(value, *, field_name):
        _ = field_name
        if "Authorization: Bearer clear-token" in value:
            raise ValueError("unsafe")

    content = (
        "[global]\n"
        "  Authorization: Bearer clear-token\n"
        "  encrypt passwords = yes\n"
        "-----BEGIN PRIVATE KEY-----\n"
        "private-material\n"
        "-----END PRIVATE KEY-----\n"
        "  workgroup = EXAMPLE\n"
    )
    redacted = SYNC.redact_secret_material(content, validator=validator)
    assert "clear-token" not in redacted
    assert "encrypt passwords = yes" not in redacted
    assert "private-material" not in redacted
    assert "workgroup = EXAMPLE" in redacted

    putty = "PuTTY-User-Key-File-3: ssh-rsa\nPrivate-Lines: 1\nprivate-material\n"
    assert SYNC.redact_secret_material(putty) == SYNC._UNSAFE_CONTENT_REDACTION


def _desired(**overrides):
    values = {
        "name": "Finance",
        "path": "/srv/shares/finance",
        "smb_enabled": True,
        "acl_spec": [{"group": "Finance-RW", "role": "rw"}],
        "snapshots_enabled": True,
        "recycle_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _observed(**overrides):
    values = {
        "name": "Finance",
        "path": "/srv/shares/finance",
        "read_only": False,
        "raw_params": {
            "valid users": "@Finance-RW",
            "vfs objects": "shadow_copy2 recycle",
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_acl_parser_preserves_quoted_group_names():
    observed = _observed(
        raw_params={
            "valid users": '"@Domain Users" @Finance-RW',
            "vfs objects": "shadow_copy2 recycle",
        }
    )
    desired = _desired(
        acl_spec=[
            {"group": "Domain Users", "role": "rw"},
            {"group": "Finance-RW", "role": "rw"},
        ]
    )
    assert SYNC.compute_drift_state(desired, observed) == "in_sync"


@pytest.mark.parametrize(
    ("desired", "observed", "expected"),
    (
        (_desired(), _observed(), "in_sync"),
        (_desired(path="/srv/shares/other"), _observed(), "drifted"),
        (_desired(), None, "missing_on_host"),
        (None, _observed(), "unmanaged"),
        (
            _desired(),
            _observed(raw_params={"_missing_on_host": True}),
            "missing_on_host",
        ),
    ),
)
def test_drift_state_matrix(desired, observed, expected):
    assert SYNC.compute_drift_state(desired, observed) == expected


def test_failure_timeout_and_partial_plans_never_replace_owned_state():
    succeeded = dict.fromkeys(SYNC.SAMBA_COLLECT_PROCEDURES, "succeeded")
    assert SYNC.classify_sync_status(succeeded) == "succeeded"
    assert all(SYNC.replacement_plan(succeeded).values())

    failed_users = {**succeeded, "service.samba.1.user_list": "failed"}
    assert SYNC.classify_sync_status(failed_users) == "partial"
    assert SYNC.replacement_plan(failed_users)["users"] is False
    assert SYNC.replacement_plan(failed_users)["groups"] is True

    timed_out_config = {**succeeded, "service.samba.1.config_test": "timed_out"}
    plan = SYNC.replacement_plan(timed_out_config)
    assert SYNC.classify_sync_status(timed_out_config) == "partial"
    assert plan["server_state"] is False
    assert plan["shares"] is False
    assert plan["users"] is True

    all_failed = dict.fromkeys(SYNC.SAMBA_COLLECT_PROCEDURES, "failed")
    assert SYNC.classify_sync_status(all_failed) == "failed"
    assert not any(SYNC.replacement_plan(all_failed).values())
