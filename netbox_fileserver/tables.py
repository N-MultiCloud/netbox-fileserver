import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

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


class SambaServerStateTable(NetBoxTable):
    domain = tables.Column(linkify=True)
    version = tables.Column(linkify=True)
    testparm_ok = columns.BooleanColumn(verbose_name="Testparm")
    observed_at = columns.DateTimeColumn(verbose_name="Observed")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaServerState
        fields = (
            "pk",
            "domain",
            "version",
            "smbd_active_state",
            "nmbd_active_state",
            "winbind_active_state",
            "samba_ad_dc_active_state",
            "testparm_ok",
            "observed_at",
            "actions",
        )
        default_columns = (
            "domain",
            "version",
            "smbd_active_state",
            "samba_ad_dc_active_state",
            "testparm_ok",
            "observed_at",
        )


class SambaConfigFileTable(NetBoxTable):
    path = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    is_primary = columns.BooleanColumn(verbose_name="Primary")
    mtime = columns.DateTimeColumn()
    fetched_at = columns.DateTimeColumn(verbose_name="Fetched")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaConfigFile
        fields = (
            "pk",
            "path",
            "domain",
            "sha256",
            "size",
            "mtime",
            "is_primary",
            "fetched_at",
            "actions",
        )
        default_columns = (
            "path",
            "domain",
            "size",
            "mtime",
            "is_primary",
            "fetched_at",
        )


class SambaConfigSnapshotTable(NetBoxTable):
    snapshot_id = tables.Column(linkify=True, verbose_name="Snapshot id")
    domain = tables.Column(linkify=True)
    created = columns.DateTimeColumn()
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaConfigSnapshot
        fields = ("pk", "snapshot_id", "domain", "created", "actions")
        default_columns = ("snapshot_id", "domain", "created")


class SambaObservedShareTable(NetBoxTable):
    name = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    browseable = columns.BooleanColumn()
    read_only = columns.BooleanColumn(verbose_name="Read only")
    guest_ok = columns.BooleanColumn(verbose_name="Guest")
    drift_state = columns.ChoiceFieldColumn(verbose_name="Drift")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaObservedShare
        fields = (
            "pk",
            "name",
            "domain",
            "path",
            "browseable",
            "read_only",
            "guest_ok",
            "drift_state",
            "actions",
        )
        default_columns = (
            "name",
            "domain",
            "path",
            "browseable",
            "read_only",
            "guest_ok",
            "drift_state",
        )


class SambaObservedUserTable(NetBoxTable):
    username = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    enabled = columns.BooleanColumn()
    last_logon = columns.DateTimeColumn(verbose_name="Last logon")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaObservedUser
        fields = (
            "pk",
            "username",
            "domain",
            "sid",
            "enabled",
            "last_logon",
            "actions",
        )
        default_columns = ("username", "domain", "sid", "enabled", "last_logon")


class SambaObservedGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaObservedGroup
        fields = ("pk", "name", "domain", "sid", "members", "actions")
        default_columns = ("name", "domain", "sid")


class SambaSessionTable(NetBoxTable):
    username = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    opened_at = columns.DateTimeColumn(verbose_name="Opened")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaSession
        fields = (
            "pk",
            "username",
            "domain",
            "machine",
            "remote_ip",
            "share",
            "pid",
            "opened_at",
            "actions",
        )
        default_columns = (
            "username",
            "domain",
            "machine",
            "remote_ip",
            "share",
            "opened_at",
        )


class SambaSyncRunTable(NetBoxTable):
    started = tables.Column(linkify=True)
    domain = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    finished = columns.DateTimeColumn()
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SambaSyncRun
        fields = (
            "pk",
            "started",
            "domain",
            "status",
            "finished",
            "rpc_execution_ids",
            "actions",
        )
        default_columns = ("started", "domain", "status", "finished")
