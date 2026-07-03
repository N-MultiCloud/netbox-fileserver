import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)


class FileServerDeploymentTable(NetBoxTable):
    fqdn = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    backend = tables.Column(linkify=True, verbose_name="Reconciler")
    vlan = tables.Column(linkify=True, verbose_name="VLAN")
    share_count = tables.Column(verbose_name="Shares")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = FileServerDeployment
        fields = (
            "pk",
            "fqdn",
            "tenant",
            "status",
            "backend",
            "vlan",
            "plan_gb",
            "plan_users",
            "share_count",
            "description",
            "actions",
        )
        default_columns = (
            "fqdn",
            "tenant",
            "status",
            "plan_gb",
            "plan_users",
            "share_count",
        )

    def render_share_count(self, value, record):
        # Use the list view's Count() annotation when present; fall back to a
        # per-row count for tables rendered without it (e.g. bulk-edit).
        return value if value is not None else record.shares.count()


class FileServerEnrollmentTokenTable(NetBoxTable):
    tenant = tables.Column(linkify=True)
    target_deployment = tables.Column(linkify=True, verbose_name="Target deployment")
    used_at = columns.DateTimeColumn(verbose_name="Used")
    expires_at = columns.DateTimeColumn(verbose_name="Expires")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = FileServerEnrollmentToken
        fields = (
            "pk",
            "tenant",
            "target_deployment",
            "expires_at",
            "used_at",
            "actions",
        )
        default_columns = ("tenant", "target_deployment", "expires_at", "used_at")


class SambaDomainTable(NetBoxTable):
    realm = tables.Column(linkify=True)
    deployment = tables.Column(linkify=True)
    netbios_name = tables.Column(verbose_name="NetBIOS")
    dc_vm = tables.Column(linkify=True, verbose_name="DC VM")
    status = columns.ChoiceFieldColumn()
    ldaps_cert_expiry = columns.DateColumn(verbose_name="LDAPS expiry")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaDomain
        fields = (
            "pk",
            "realm",
            "deployment",
            "netbios_name",
            "dc_vm",
            "functional_level",
            "ldaps_cert_expiry",
            "status",
            "actions",
        )
        default_columns = (
            "realm",
            "deployment",
            "netbios_name",
            "dc_vm",
            "status",
            "ldaps_cert_expiry",
        )


class NextcloudInstanceTable(NetBoxTable):
    deployment = tables.Column(linkify=True)
    vm = tables.Column(linkify=True)
    ip = tables.Column(linkify=True)
    version = tables.Column()
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = NextcloudInstance
        fields = (
            "pk",
            "deployment",
            "vm",
            "ip",
            "version",
            "ldap_config_id",
            "status",
            "actions",
        )
        default_columns = ("deployment", "vm", "ip", "version", "status")


class FileShareTable(NetBoxTable):
    name = tables.Column(linkify=True)
    deployment = tables.Column(linkify=True)
    path = tables.Column()
    smb_enabled = columns.BooleanColumn(verbose_name="SMB")
    snapshots_enabled = columns.BooleanColumn(verbose_name="Snapshots")
    recycle_enabled = columns.BooleanColumn(verbose_name="Recycle")
    nc_mount_enabled = columns.BooleanColumn(verbose_name="NC mount")
    notify_active = columns.BooleanColumn(verbose_name="Notify")
    status = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = FileShare
        fields = (
            "pk",
            "name",
            "deployment",
            "path",
            "smb_enabled",
            "snapshots_enabled",
            "recycle_enabled",
            "nc_mount_enabled",
            "nc_mount_point",
            "notify_active",
            "status",
            "actions",
        )
        default_columns = (
            "name",
            "deployment",
            "path",
            "smb_enabled",
            "nc_mount_enabled",
            "notify_active",
            "status",
        )


class DomainGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    description = tables.Column()
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = DomainGroup
        fields = ("pk", "name", "domain", "description", "actions")
        default_columns = ("name", "domain", "description")
