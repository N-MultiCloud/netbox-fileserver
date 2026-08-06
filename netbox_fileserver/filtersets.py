import django_filters
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.models import Tenant

from .choices import (
    DeploymentStatusChoices,
    SambaDriftStateChoices,
    SambaSyncStatusChoices,
)
from .models import (
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


class FileServerDeploymentFilterSet(NetBoxModelFilterSet):
    fqdn = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.MultipleChoiceFilter(choices=DeploymentStatusChoices)
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(), field_name="tenant"
    )

    class Meta:
        model = FileServerDeployment
        fields = ("id", "fqdn", "status", "tenant_id", "plan_gb", "plan_users")


class FileServerEnrollmentTokenFilterSet(NetBoxModelFilterSet):
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(), field_name="tenant"
    )
    target_deployment_id = django_filters.ModelMultipleChoiceFilter(
        queryset=FileServerDeployment.objects.all(), field_name="target_deployment"
    )
    used = django_filters.BooleanFilter(method="filter_used")

    class Meta:
        model = FileServerEnrollmentToken
        fields = ("id", "tenant_id", "target_deployment_id", "expires_at", "used")

    def filter_used(self, queryset, _name, value):
        if value:
            return queryset.exclude(used_at__isnull=True)
        return queryset.filter(used_at__isnull=True)


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


class SambaServerStateFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    version = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SambaServerState
        fields = (
            "id",
            "domain_id",
            "version",
            "smbd_active_state",
            "nmbd_active_state",
            "winbind_active_state",
            "samba_ad_dc_active_state",
            "testparm_ok",
            "observed_at",
        )


class SambaConfigFileFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    path = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SambaConfigFile
        fields = (
            "id",
            "domain_id",
            "path",
            "sha256",
            "is_primary",
            "mtime",
            "fetched_at",
        )


class SambaConfigSnapshotFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    snapshot_id = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SambaConfigSnapshot
        fields = ("id", "domain_id", "snapshot_id", "created")


class SambaObservedShareFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    name = django_filters.CharFilter(lookup_expr="icontains")
    path = django_filters.CharFilter(lookup_expr="icontains")
    drift_state = django_filters.MultipleChoiceFilter(choices=SambaDriftStateChoices)

    class Meta:
        model = SambaObservedShare
        fields = (
            "id",
            "domain_id",
            "name",
            "path",
            "browseable",
            "read_only",
            "guest_ok",
            "drift_state",
        )


class SambaObservedUserFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    username = django_filters.CharFilter(lookup_expr="icontains")
    sid = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SambaObservedUser
        fields = ("id", "domain_id", "username", "sid", "enabled", "last_logon")


class SambaObservedGroupFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    name = django_filters.CharFilter(lookup_expr="icontains")
    sid = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SambaObservedGroup
        fields = ("id", "domain_id", "name", "sid")


class SambaSessionFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    username = django_filters.CharFilter(lookup_expr="icontains")
    machine = django_filters.CharFilter(lookup_expr="icontains")
    share = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SambaSession
        fields = (
            "id",
            "domain_id",
            "username",
            "machine",
            "remote_ip",
            "share",
            "pid",
            "opened_at",
        )


class SambaSyncRunFilterSet(NetBoxModelFilterSet):
    domain_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SambaDomain.objects.all(), field_name="domain"
    )
    status = django_filters.MultipleChoiceFilter(choices=SambaSyncStatusChoices)

    class Meta:
        model = SambaSyncRun
        fields = ("id", "domain_id", "status", "started", "finished")
