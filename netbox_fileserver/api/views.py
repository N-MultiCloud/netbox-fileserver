from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from ..choices import DeploymentStatusChoices
from ..filtersets import (
    DomainGroupFilterSet,
    FileServerDeploymentFilterSet,
    FileServerEnrollmentTokenFilterSet,
    FileShareFilterSet,
    NextcloudInstanceFilterSet,
    SambaConfigFileFilterSet,
    SambaConfigSnapshotFilterSet,
    SambaDomainFilterSet,
    SambaObservedGroupFilterSet,
    SambaObservedShareFilterSet,
    SambaObservedUserFilterSet,
    SambaServerStateFilterSet,
    SambaSessionFilterSet,
    SambaSyncRunFilterSet,
)
from ..models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaConfigFile,
    SambaConfigSnapshot,
    SambaDomain,
    SambaObservedGroup,
    SambaObservedShare,
    SambaObservedUser,
    SambaServerState,
    SambaSession,
    SambaSyncRun,
)
from .serializers import (
    DomainGroupSerializer,
    FileServerAgentEnrollSerializer,
    FileServerDeploymentApproveSerializer,
    FileServerDeploymentReconcilerSerializer,
    FileServerDeploymentSerializer,
    FileServerEnrollmentTokenSerializer,
    FileShareSerializer,
    NextcloudInstanceSerializer,
    SambaConfigFileSerializer,
    SambaConfigSnapshotSerializer,
    SambaDomainSerializer,
    SambaObservedGroupSerializer,
    SambaObservedShareSerializer,
    SambaObservedUserSerializer,
    SambaServerStateSerializer,
    SambaSessionSerializer,
    SambaSyncRunSerializer,
)

FILESERVER_RECONCILER_GROUP_NAME = "File Server Reconcilers"


def _raise_drf_validation(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError({"detail": exc.messages}) from exc


def _is_tenant_admin(user, tenant) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    slug = getattr(tenant, "slug", "")
    if not slug:
        return False
    return user.groups.filter(name=f"Cloud Portal: {slug} :: Admins").exists()


def _is_reconciler_service_account(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=FILESERVER_RECONCILER_GROUP_NAME).exists()


def _token_context_payload(token: FileServerEnrollmentToken, agent_payload: dict) -> dict:
    deployment = token.target_deployment
    payload = {
        "enrollment_token": {
            "id": token.pk,
            "expires_at": token.expires_at,
            "used_at": token.used_at,
        },
        "tenant": {
            "id": token.tenant_id,
            "name": token.tenant.name,
            "slug": token.tenant.slug,
            "display": str(token.tenant),
        },
        "deployment": None,
        "agent": {
            "vmid": agent_payload["vmid"],
            "hostname": agent_payload["hostname"],
            "ips": agent_payload["ips"],
            "realm": agent_payload["realm"],
            "netbios": agent_payload["netbios"],
        },
    }
    if deployment is not None:
        payload["deployment"] = {
            "id": deployment.pk,
            "display": str(deployment),
            "fqdn": deployment.fqdn,
            "status": deployment.status,
        }
    return payload


class FileServerDeploymentViewSet(NetBoxModelViewSet):
    queryset = FileServerDeployment.objects.select_related(
        "tenant", "backend", "vlan", "prefix"
    ).prefetch_related("tags")
    serializer_class = FileServerDeploymentSerializer
    filterset_class = FileServerDeploymentFilterSet

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"} and _is_reconciler_service_account(
            self.request.user
        ):
            return FileServerDeploymentReconcilerSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        queryset = (
            FileServerDeployment.objects.restrict(request.user, "change")
            .select_related("tenant", "backend", "vlan", "prefix")
            .prefetch_related("tags")
        )
        deployment = get_object_or_404(queryset, pk=pk)
        if not _is_tenant_admin(request.user, deployment.tenant):
            raise PermissionDenied(
                "Staff or a tenant admin for this deployment is required."
            )
        serializer = FileServerDeploymentApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_status = serializer.validated_data.get(
            "status", DeploymentStatusChoices.STATUS_PLANNED
        )
        try:
            deployment.approve(status=target_status)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(
            self.get_serializer(deployment, context=self.get_serializer_context()).data
        )


class FileServerEnrollmentTokenViewSet(NetBoxModelViewSet):
    queryset = FileServerEnrollmentToken.objects.select_related(
        "tenant", "target_deployment"
    ).prefetch_related("tags")
    serializer_class = FileServerEnrollmentTokenSerializer
    filterset_class = FileServerEnrollmentTokenFilterSet

    @action(detail=False, methods=["post"], url_path="consume")
    def consume(self, request):
        # This remains a global reconciler service identity boundary. Do not grant
        # tenant-scoped users this permission; object-less checks match any holder
        # of a constrained grant before the submitted token is known.
        if not request.user.has_perm(
            "netbox_fileserver.change_fileserverenrollmenttoken"
        ):
            raise PermissionDenied(
                "change_fileserverenrollmenttoken permission is required."
            )
        serializer = FileServerAgentEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = FileServerEnrollmentToken.consume_plaintext(
                serializer.validated_data["token"]
            )
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        token = FileServerEnrollmentToken.objects.select_related(
            "tenant", "target_deployment"
        ).get(pk=token.pk)
        return Response(_token_context_payload(token, serializer.validated_data))


class SambaDomainViewSet(NetBoxModelViewSet):
    queryset = SambaDomain.objects.select_related(
        "deployment", "dc_vm", "dc_ip"
    ).prefetch_related("tags")
    serializer_class = SambaDomainSerializer
    filterset_class = SambaDomainFilterSet

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):
        queryset = (
            SambaDomain.objects.restrict(request.user, "change")
            .select_related("deployment__tenant", "dc_vm", "dc_ip")
            .prefetch_related("tags")
        )
        domain = get_object_or_404(queryset, pk=pk)
        if not (
            _is_tenant_admin(request.user, domain.deployment.tenant)
            or _is_reconciler_service_account(request.user)
        ):
            raise PermissionDenied(
                "Staff, a tenant admin, or a File Server Reconciler is required."
            )
        for permission in (
            "netbox_rpc.execute_rpcintent",
            "netbox_rpc.execute_rpcprocedure",
        ):
            if not request.user.has_perm(permission):
                raise PermissionDenied(f"{permission} permission is required.")

        with transaction.atomic():
            locked_domain = SambaDomain.objects.select_for_update().get(pk=domain.pk)
            if SambaSyncRun.objects.filter(
                domain=locked_domain,
                status="running",
            ).exists():
                return Response(
                    {"detail": "A Samba sync is already running for this domain."},
                    status=http_status.HTTP_409_CONFLICT,
                )
            sync_run = SambaSyncRun(domain=locked_domain)
            sync_run.full_clean()
            sync_run.save()

        from ..jobs import SambaSyncJob

        try:
            job = SambaSyncJob.enqueue(
                sync_run_pk=sync_run.pk,
                domain_pk=domain.pk,
                requester_pk=request.user.pk,
                user=request.user,
                name=f"Samba Sync: {domain}",
            )
        except Exception:
            from ..samba_sync import _finish_sync_run

            _finish_sync_run(
                sync_run,
                status="failed",
                errors=["The Samba sync job could not be enqueued."],
            )
            return Response(
                {
                    "detail": "The Samba sync job could not be enqueued.",
                    "sync_run": sync_run.pk,
                },
                status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = {
            "detail": "Samba sync job enqueued.",
            "domain": domain.pk,
            "sync_run": sync_run.pk,
            "job": getattr(job, "pk", None) or getattr(job, "id", None),
        }
        if hasattr(job, "get_absolute_url"):
            payload["url"] = job.get_absolute_url()
        return Response(payload, status=http_status.HTTP_202_ACCEPTED)


class NextcloudInstanceViewSet(NetBoxModelViewSet):
    queryset = NextcloudInstance.objects.select_related(
        "deployment", "vm", "ip"
    ).prefetch_related("tags")
    serializer_class = NextcloudInstanceSerializer
    filterset_class = NextcloudInstanceFilterSet


class FileShareViewSet(NetBoxModelViewSet):
    queryset = FileShare.objects.select_related("deployment").prefetch_related("tags")
    serializer_class = FileShareSerializer
    filterset_class = FileShareFilterSet


class DomainGroupViewSet(NetBoxModelViewSet):
    queryset = DomainGroup.objects.select_related("domain").prefetch_related("tags")
    serializer_class = DomainGroupSerializer
    filterset_class = DomainGroupFilterSet


class SambaServerStateViewSet(NetBoxModelViewSet):
    queryset = SambaServerState.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaServerStateSerializer
    filterset_class = SambaServerStateFilterSet


class SambaConfigFileViewSet(NetBoxModelViewSet):
    queryset = SambaConfigFile.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaConfigFileSerializer
    filterset_class = SambaConfigFileFilterSet


class SambaConfigSnapshotViewSet(NetBoxModelViewSet):
    queryset = SambaConfigSnapshot.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaConfigSnapshotSerializer
    filterset_class = SambaConfigSnapshotFilterSet


class SambaObservedShareViewSet(NetBoxModelViewSet):
    queryset = SambaObservedShare.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaObservedShareSerializer
    filterset_class = SambaObservedShareFilterSet


class SambaObservedUserViewSet(NetBoxModelViewSet):
    queryset = SambaObservedUser.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaObservedUserSerializer
    filterset_class = SambaObservedUserFilterSet


class SambaObservedGroupViewSet(NetBoxModelViewSet):
    queryset = SambaObservedGroup.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaObservedGroupSerializer
    filterset_class = SambaObservedGroupFilterSet


class SambaSessionViewSet(NetBoxModelViewSet):
    queryset = SambaSession.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaSessionSerializer
    filterset_class = SambaSessionFilterSet


class SambaSyncRunViewSet(NetBoxModelViewSet):
    queryset = SambaSyncRun.objects.select_related("domain").prefetch_related("tags")
    serializer_class = SambaSyncRunSerializer
    filterset_class = SambaSyncRunFilterSet
