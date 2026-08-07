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
# SambaSyncJob occupies one worker for its own duration while it dispatches
# and polls for its child RPC executions, which compete for the same queue.
# With fewer than this many workers registered, a domain sync can never
# finish: the dispatching job holds its worker for the full poll loop while
# no worker is ever free to run a single child, guaranteeing every sync
# times out at SAMBA_SYNC_JOB_TIMEOUT instead of degrading to serialized-but-
# eventually-successful execution. See docs/samba-observed-state.md.
MIN_SAMBA_SYNC_WORKERS = 2


def registered_worker_count(queue_name: str = SAMBA_SYNC_QUEUE_NAME) -> int:
    """Count RQ workers currently registered against a queue.

    This is a tripwire, not a live-concurrency guarantee: a registered
    worker can still be busy on unrelated jobs on the same queue. It only
    catches the topology that has *zero* chance of ever completing a sync,
    so a caller gets an immediate, clear rejection instead of a silent
    300-second timeout.
    """
    import django_rq
    from rq import Worker

    return len(Worker.all(queue=django_rq.get_queue(queue_name)))


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
        if sync_run.status != "running":
            # The stale-recovery path in api/views.py's sync() action already
            # reconciled this run to a terminal status (its linked core.Job
            # died or outran its timeout, and a new run took its place)
            # before this straggler execution got a worker slot. Folding
            # results into an already-terminal run would race the writer
            # that superseded it, so bail out without touching it further.
            return
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
    "MIN_SAMBA_SYNC_WORKERS",
    "SAMBA_SYNC_JOB_TIMEOUT",
    "SAMBA_SYNC_POLL_INTERVAL_SECONDS",
    "SAMBA_SYNC_QUEUE_NAME",
    "SAMBA_SYNC_TIMEOUT_SECONDS",
    "SambaSyncJob",
    "registered_worker_count",
)
