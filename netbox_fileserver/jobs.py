"""NetBox RQ job for the RPC-driven Samba observed-state sweep."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from netbox.constants import RQ_QUEUE_DEFAULT
from netbox.jobs import JobRunner

from .models import SambaDomain, SambaSyncRun
from .samba_sync import SambaSyncIncomplete, perform_samba_sync

SAMBA_SYNC_QUEUE_NAME = RQ_QUEUE_DEFAULT
SAMBA_SYNC_TIMEOUT_SECONDS = 300
SAMBA_SYNC_POLL_INTERVAL_SECONDS = 2
SAMBA_SYNC_JOB_TIMEOUT = SAMBA_SYNC_TIMEOUT_SECONDS + 60


class SambaSyncJob(JobRunner):
    """Dispatch and fold one ``fileserver.samba.collect_state`` intent."""

    class Meta:
        name = "File Server Samba Sync"

    @classmethod
    def enqueue(
        cls,
        *,
        sync_run_pk: int,
        domain_pk: int,
        requester_pk: int,
        **kwargs: object,
    ):
        if kwargs.pop("instance", None) is not None:
            raise ValueError("Use domain_pk; Samba sync jobs are not object-attached.")
        kwargs.setdefault("queue_name", SAMBA_SYNC_QUEUE_NAME)
        kwargs.setdefault("job_timeout", SAMBA_SYNC_JOB_TIMEOUT)
        data = dict(kwargs.pop("data", {}) or {})
        data["samba_sync"] = {
            "sync_run_pk": sync_run_pk,
            "domain_pk": domain_pk,
            "requester_pk": requester_pk,
        }
        job = super().enqueue(
            sync_run_pk=sync_run_pk,
            domain_pk=domain_pk,
            requester_pk=requester_pk,
            data=data,
            **kwargs,
        )
        job.data = data
        job.save(update_fields=("data",))
        return job

    def run(
        self,
        *,
        sync_run_pk: int,
        domain_pk: int,
        requester_pk: int,
        **_kwargs: object,
    ) -> None:
        sync_run = SambaSyncRun.objects.select_related("domain").get(pk=sync_run_pk)
        domain = SambaDomain.objects.select_related("deployment").get(pk=domain_pk)
        user = get_user_model().objects.filter(pk=requester_pk).first()
        if user is None:
            from .samba_sync import _finish_sync_run

            _finish_sync_run(
                sync_run,
                status="failed",
                errors=["The requesting user no longer exists."],
            )
            raise SambaSyncIncomplete(f"Samba sync run {sync_run.pk} failed.")
        perform_samba_sync(
            sync_run=sync_run,
            domain=domain,
            user=user,
            timeout_seconds=SAMBA_SYNC_TIMEOUT_SECONDS,
            poll_interval_seconds=SAMBA_SYNC_POLL_INTERVAL_SECONDS,
        )


__all__ = (
    "SAMBA_SYNC_JOB_TIMEOUT",
    "SAMBA_SYNC_POLL_INTERVAL_SECONDS",
    "SAMBA_SYNC_QUEUE_NAME",
    "SAMBA_SYNC_TIMEOUT_SECONDS",
    "SambaSyncJob",
)
