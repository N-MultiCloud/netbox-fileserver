import django_filters
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.models import Tenant

from .choices import DeploymentStatusChoices
from .models import (
    DomainGroup,
    FileServerDeployment,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)


class FileServerDeploymentFilterSet(NetBoxModelFilterSet):
    fqdn = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.MultipleChoiceFilter(choices=DeploymentStatusChoices)
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(), field_name="tenant"
    )

    class Meta:
        model = FileServerDeployment
        fields = ("id", "fqdn", "status", "tenant_id", "plan_gb", "plan_users")


class SambaDomainFilterSet(NetBoxModelFilterSet):
    realm = django_filters.CharFilter(lookup_expr="icontains")
    netbios_name = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.MultipleChoiceFilter(choices=DeploymentStatusChoices)
    deployment_id = django_filters.ModelMultipleChoiceFilter(
        queryset=FileServerDeployment.objects.all(), field_name="deployment"
    )

    class Meta:
        model = SambaDomain
        fields = ("id", "realm", "netbios_name", "status", "deployment_id", "functional_level")


class NextcloudInstanceFilterSet(NetBoxModelFilterSet):
    version = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.MultipleChoiceFilter(choices=DeploymentStatusChoices)
    deployment_id = django_filters.ModelMultipleChoiceFilter(
        queryset=FileServerDeployment.objects.all(), field_name="deployment"
    )

    class Meta:
        model = NextcloudInstance
        fields = ("id", "version", "status", "deployment_id", "ldap_config_id")


class FileShareFilterSet(NetBoxModelFilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    path = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.MultipleChoiceFilter(choices=DeploymentStatusChoices)
    deployment_id = django_filters.ModelMultipleChoiceFilter(
        queryset=FileServerDeployment.objects.all(), field_name="deployment"
    )

    class Meta:
        model = FileShare
        fields = (
            "id",
            "name",
            "path",
            "status",
            "deployment_id",
            "smb_enabled",
            "snapshots_enabled",
            "recycle_enabled",
            "nc_mount_enabled",
            "notify_active",
        )


class DomainGroupFilterSet(NetBoxModelFilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )

    class Meta:
        model = DomainGroup
        fields = ("id", "name", "domain_id")
