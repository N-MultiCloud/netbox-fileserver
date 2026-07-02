from netbox.api.viewsets import NetBoxModelViewSet

from ..models import (
    DomainGroup,
    FileServerDeployment,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)
from .serializers import (
    DomainGroupSerializer,
    FileServerDeploymentSerializer,
    FileShareSerializer,
    NextcloudInstanceSerializer,
    SambaDomainSerializer,
)


class FileServerDeploymentViewSet(NetBoxModelViewSet):
    queryset = FileServerDeployment.objects.select_related(
        "tenant", "backend", "vlan", "prefix"
    ).prefetch_related("tags")
    serializer_class = FileServerDeploymentSerializer


class SambaDomainViewSet(NetBoxModelViewSet):
    queryset = SambaDomain.objects.select_related(
        "deployment", "dc_vm", "dc_ip"
    ).prefetch_related("tags")
    serializer_class = SambaDomainSerializer


class NextcloudInstanceViewSet(NetBoxModelViewSet):
    queryset = NextcloudInstance.objects.select_related(
        "deployment", "vm", "ip"
    ).prefetch_related("tags")
    serializer_class = NextcloudInstanceSerializer


class FileShareViewSet(NetBoxModelViewSet):
    queryset = FileShare.objects.select_related("deployment").prefetch_related("tags")
    serializer_class = FileShareSerializer


class DomainGroupViewSet(NetBoxModelViewSet):
    queryset = DomainGroup.objects.select_related("domain").prefetch_related("tags")
    serializer_class = DomainGroupSerializer
