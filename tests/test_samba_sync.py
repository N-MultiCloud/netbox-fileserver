"""Pure unit tests for the RPC Samba fold, redaction, and drift engine."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import UTC, datetime, timedelta
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


def test_redaction_handles_backslash_continued_sensitive_assignment():
    content = (
        "[global]\n"
        "  smb passwd file = \\\n"
        "  s3cr3t-continuation-value\n"
        "  workgroup = EXAMPLE\n"
    )
    redacted = SYNC.redact_secret_material(content)
    assert "s3cr3t-continuation-value" not in redacted
    assert "smb passwd file = [REDACTED]" in redacted
    assert "workgroup = EXAMPLE" in redacted


def test_redaction_preserves_non_sensitive_continued_assignment():
    content = (
        "[global]\n"
        "  include = /etc/samba/dc1.conf \\\n"
        "  /etc/samba/dc2.conf\n"
        "  workgroup = EXAMPLE\n"
    )
    redacted = SYNC.redact_secret_material(content)
    assert "/etc/samba/dc1.conf" in redacted
    assert "/etc/samba/dc2.conf" in redacted
    assert "workgroup = EXAMPLE" in redacted


def test_config_read_truncated_content_fails_the_whole_collection():
    result = {
        "path": "/etc/samba/smb.conf",
        "sha256": "deadbeef",
        "content": (
            "[global]\n  workgroup = EXAMPLE\n[Finance]\n  path = /srv"
            "...[truncated]"
        ),
    }
    with pytest.raises(SYNC.SambaResultTruncated):
        SYNC.fold_result(
            "service.samba.1.config_read", result, model_classes=MODEL_CLASSES
        )


def test_config_test_truncated_stdout_fails_the_whole_collection():
    result = {
        "valid": True,
        "stdout": "[Finance]\n  path = /srv/finance...[truncated]",
    }
    with pytest.raises(SYNC.SambaResultTruncated):
        SYNC.fold_result(
            "service.samba.1.config_test", result, model_classes=MODEL_CLASSES
        )


def test_status_report_truncated_sessions_fails_the_whole_collection():
    result = {
        "sessions": [
            {"session_id": "1", "pid": 100, "username": "alice"},
            {"_truncated": True, "remaining": 12},
        ],
        "tcons": [],
    }
    with pytest.raises(SYNC.SambaResultTruncated):
        SYNC.fold_result(
            "service.samba.1.status_report", result, model_classes=MODEL_CLASSES
        )


def test_status_report_truncated_tcons_fails_the_whole_collection():
    result = {
        "sessions": [],
        "tcons": [
            {"session_id": "1", "pid": 100, "service": "finance"},
            {"_truncated": True, "remaining": 5},
        ],
    }
    with pytest.raises(SYNC.SambaResultTruncated):
        SYNC.fold_result(
            "service.samba.1.status_report", result, model_classes=MODEL_CLASSES
        )


def test_status_report_untruncated_sessions_fold_normally():
    result = {
        "sessions": [{"session_id": "1", "pid": 100, "username": "alice"}],
        "tcons": [],
    }
    instances = SYNC.fold_result(
        "service.samba.1.status_report", result, model_classes=MODEL_CLASSES
    )
    assert len(instances) == 1


def test_truncated_status_report_is_downgraded_to_fold_failed_and_blocks_replacement():
    statuses = dict.fromkeys(SYNC.SAMBA_COLLECT_PROCEDURES, "succeeded")
    statuses["service.samba.1.status_report"] = "fold_failed"
    plan = SYNC.replacement_plan(statuses)
    assert plan["sessions"] is False
    assert plan["server_state"] is True
    assert plan["shares"] is True
    assert SYNC.classify_sync_status(statuses, has_fold_error=True) == "partial"


def test_truncated_config_read_is_downgraded_to_fold_failed_and_blocks_replacement():
    statuses = dict.fromkeys(SYNC.SAMBA_COLLECT_PROCEDURES, "succeeded")
    statuses["service.samba.1.config_read"] = "fold_failed"
    plan = SYNC.replacement_plan(statuses)
    assert plan["config"] is False
    assert plan["server_state"] is False
    assert plan["shares"] is True
    assert SYNC.classify_sync_status(statuses, has_fold_error=True) == "partial"


def test_truncated_config_test_is_downgraded_to_fold_failed_and_blocks_replacement():
    statuses = dict.fromkeys(SYNC.SAMBA_COLLECT_PROCEDURES, "succeeded")
    statuses["service.samba.1.config_test"] = "fold_failed"
    plan = SYNC.replacement_plan(statuses)
    assert plan["server_state"] is False
    assert plan["shares"] is False
    assert plan["config"] is True
    assert SYNC.classify_sync_status(statuses, has_fold_error=True) == "partial"


def test_stale_run_with_no_linked_job_is_not_stale_within_grace_period():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert not SYNC.is_sync_run_stale(
        job_status=None,
        job_started=None,
        run_started=now - timedelta(seconds=5),
        now=now,
        job_timeout_seconds=360,
    )


def test_stale_run_with_no_linked_job_is_stale_past_grace_period():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert SYNC.is_sync_run_stale(
        job_status=None,
        job_started=None,
        run_started=now - timedelta(seconds=31),
        now=now,
        job_timeout_seconds=360,
    )


def test_stale_run_with_terminal_job_is_always_stale():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for status in ("completed", "errored", "failed"):
        assert SYNC.is_sync_run_stale(
            job_status=status,
            job_started=now - timedelta(seconds=1),
            run_started=now - timedelta(seconds=1),
            now=now,
            job_timeout_seconds=360,
        )


def test_stale_run_with_pending_or_scheduled_job_is_not_stale_within_backstop():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for status in ("pending", "scheduled"):
        assert not SYNC.is_sync_run_stale(
            job_status=status,
            job_started=None,
            run_started=now - timedelta(minutes=30),
            now=now,
            job_timeout_seconds=360,
        )


def test_stale_run_with_pending_or_scheduled_job_is_stale_past_backstop():
    # A pending/scheduled job that never reaches a terminal or running
    # status -- because it was permanently lost (Redis eviction, a purged
    # queue, or a worker that fetched it and died before calling
    # Job.start()) -- must not wedge the domain in "running" forever; it is
    # eventually reconciled once the row's age crosses the generous
    # pending-job backstop.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for status in ("pending", "scheduled"):
        assert SYNC.is_sync_run_stale(
            job_status=status,
            job_started=None,
            run_started=now - timedelta(hours=2),
            now=now,
            job_timeout_seconds=360,
        )


def test_stale_run_with_running_job_within_its_own_timeout_is_not_stale():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert not SYNC.is_sync_run_stale(
        job_status="running",
        job_started=now - timedelta(seconds=100),
        run_started=now - timedelta(hours=6),
        job_timeout_seconds=360,
        now=now,
    )


def test_stale_run_with_running_job_past_its_own_timeout_is_stale():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert SYNC.is_sync_run_stale(
        job_status="running",
        job_started=now - timedelta(seconds=361),
        run_started=now - timedelta(seconds=361),
        job_timeout_seconds=360,
        now=now,
    )


def test_stale_run_with_running_job_queued_a_long_time_before_started_is_not_stale():
    # A job that sat queued behind other work for a long time before its
    # execution actually began must not be penalized for queue wait -- only
    # its own execution time (since job.started) counts against the timeout.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert not SYNC.is_sync_run_stale(
        job_status="running",
        job_started=now - timedelta(seconds=10),
        run_started=now - timedelta(hours=6),
        job_timeout_seconds=360,
        now=now,
    )


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
