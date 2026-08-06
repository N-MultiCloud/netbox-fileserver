from django.core.exceptions import ValidationError as DjangoValidationError
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ..choices import DeploymentStatusChoices
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
    validate_no_secret_material,
)


class SecretSafeObservedSerializerMixin:
    """Reject embedded credential material from reconciler-owned payloads."""

    secret_safe_fields: tuple[str, ...] = ()

    def validate(self, data):
        # NetBox's custom-fields serializer may expose the input name or its
        # custom_field_data source in validated_data depending on the version.
        # Guard both so inherited custom fields cannot become a secret bypass.
        for field_name in (*self.secret_safe_fields, "custom_fields", "custom_field_data"):
            if field_name not in data:
                continue
            try:
                validate_no_secret_material(data[field_name], field_name=field_name)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
        return super().validate(data)


class FileServerDeploymentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:fileserverdeployment-detail"
    )

    class Meta:
        model = FileServerDeployment
        # FK fields (tenant, backend, vlan, prefix) are auto-resolved by
        # NetBoxModelSerializer to nested brief serializers on read and accept a
        # PK on write.
        fields = (
            "id",
            "url",
            "display",
            "tenant",
            "status",
            "backend",
            "vlan",
            "prefix",
            "plan_gb",
            "plan_users",
            "fqdn",
            "secret_ref",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("status", "created", "last_updated")


class FileServerDeploymentReconcilerSerializer(FileServerDeploymentSerializer):
    class Meta(FileServerDeploymentSerializer.Meta):
        read_only_fields = ("created", "last_updated")

    def update(self, instance, validated_data):
        allow_status_write = (
            "status" in validated_data and validated_data["status"] != instance.status
        )
        if allow_status_write:
            instance.allow_reconciler_status_write()
        return super().update(instance, validated_data)


class FileServerDeploymentApproveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(
            DeploymentStatusChoices.STATUS_PLANNED,
            DeploymentStatusChoices.STATUS_ACTIVE,
        ),
        default=DeploymentStatusChoices.STATUS_PLANNED,
        required=False,
    )


class FileServerEnrollmentTokenSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:fileserverenrollmenttoken-detail"
    )
    token = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(required=False)

    class Meta:
        model = FileServerEnrollmentToken
        fields = (
            "id",
            "url",
            "display",
            "token",
            "tenant",
            "target_deployment",
            "expires_at",
            "used_at",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = (
            "token",
            "used_at",
            "created",
            "last_updated",
        )

    def validate(self, data):
        if self.instance is None:
            plaintext = FileServerEnrollmentToken.generate_plaintext()
            self._plaintext_token = plaintext
            data["token_hash"] = FileServerEnrollmentToken.hash_plaintext(plaintext)
            data.setdefault("expires_at", FileServerEnrollmentToken.default_expires_at())
        return super().validate(data)

    def create(self, validated_data):
        instance = super().create(validated_data)
        if plaintext := getattr(self, "_plaintext_token", None):
            instance._plaintext_token = plaintext
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        plaintext = getattr(instance, "_plaintext_token", None)
        if plaintext:
            data["token"] = plaintext
        return data


class FileServerAgentEnrollSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, trim_whitespace=True)
    vmid = serializers.IntegerField(min_value=1)
    hostname = serializers.CharField(max_length=255, trim_whitespace=True)
    ips = serializers.ListField(
        child=serializers.IPAddressField(),
        allow_empty=False,
    )
    realm = serializers.RegexField(
        regex=r"^[A-Z0-9]([A-Z0-9-]{0,61}[A-Z0-9])?(\.[A-Z0-9]([A-Z0-9-]{0,61}[A-Z0-9])?)+$",
        max_length=255,
    )
    netbios = serializers.RegexField(
        regex=r"^[A-Z0-9]([A-Z0-9-]{0,13}[A-Z0-9])?$",
        max_length=15,
    )

    def validate(self, data):
        data["hostname"] = data["hostname"].lower()
        data["realm"] = data["realm"].upper()
        data["netbios"] = data["netbios"].upper()
        data["enrollment_token"] = FileServerEnrollmentToken.get_valid_for_plaintext(
            data["token"]
        )
        return data


class SambaDomainSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambadomain-detail"
    )

    class Meta:
        model = SambaDomain
        fields = (
            "id",
            "url",
            "display",
            "deployment",
            "realm",
            "netbios_name",
            "dc_vm",
            "dc_ip",
            "ldaps_cert_expiry",
            "functional_level",
            "status",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class NextcloudInstanceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:nextcloudinstance-detail"
    )

    class Meta:
        model = NextcloudInstance
        fields = (
            "id",
            "url",
            "display",
            "deployment",
            "vm",
            "ip",
            "version",
            "ldap_config_id",
            "status",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class FileShareSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:fileshare-detail"
    )

    class Meta:
        model = FileShare
        fields = (
            "id",
            "url",
            "display",
            "deployment",
            "name",
            "path",
            "description",
            "smb_enabled",
            "acl_spec",
            "snapshots_enabled",
            "recycle_enabled",
            "nc_mount_enabled",
            "nc_mount_id",
            "nc_mount_point",
            "notify_active",
            "status",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class DomainGroupSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:domaingroup-detail"
    )

    class Meta:
        model = DomainGroup
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "name",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaServerStateSerializer(
    SecretSafeObservedSerializerMixin, NetBoxModelSerializer
):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambaserverstate-detail"
    )
    secret_safe_fields = (
        "version",
        "smbd_active_state",
        "smbd_sub_state",
        "smbd_unit_file_state",
        "nmbd_active_state",
        "nmbd_sub_state",
        "nmbd_unit_file_state",
        "winbind_active_state",
        "winbind_sub_state",
        "winbind_unit_file_state",
        "samba_ad_dc_active_state",
        "samba_ad_dc_sub_state",
        "samba_ad_dc_unit_file_state",
        "config_sha256",
    )

    class Meta:
        model = SambaServerState
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "version",
            "smbd_active_state",
            "smbd_sub_state",
            "smbd_unit_file_state",
            "nmbd_active_state",
            "nmbd_sub_state",
            "nmbd_unit_file_state",
            "winbind_active_state",
            "winbind_sub_state",
            "winbind_unit_file_state",
            "samba_ad_dc_active_state",
            "samba_ad_dc_sub_state",
            "samba_ad_dc_unit_file_state",
            "config_sha256",
            "testparm_ok",
            "observed_at",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaConfigFileSerializer(
    SecretSafeObservedSerializerMixin, NetBoxModelSerializer
):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambaconfigfile-detail"
    )
    secret_safe_fields = ("path", "content")

    class Meta:
        model = SambaConfigFile
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "path",
            "content",
            "sha256",
            "size",
            "mtime",
            "is_primary",
            "fetched_at",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaConfigSnapshotSerializer(
    SecretSafeObservedSerializerMixin, NetBoxModelSerializer
):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambaconfigsnapshot-detail"
    )
    secret_safe_fields = ("snapshot_id", "content")

    class Meta:
        model = SambaConfigSnapshot
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "snapshot_id",
            "content",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaObservedShareSerializer(
    SecretSafeObservedSerializerMixin, NetBoxModelSerializer
):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambaobservedshare-detail"
    )
    secret_safe_fields = ("name", "path", "raw_params")

    class Meta:
        model = SambaObservedShare
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "name",
            "path",
            "raw_params",
            "browseable",
            "read_only",
            "guest_ok",
            "drift_state",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaObservedUserSerializer(
    SecretSafeObservedSerializerMixin, NetBoxModelSerializer
):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambaobserveduser-detail"
    )
    secret_safe_fields = ("username", "sid")

    class Meta:
        model = SambaObservedUser
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "username",
            "sid",
            "enabled",
            "last_logon",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaObservedGroupSerializer(
    SecretSafeObservedSerializerMixin, NetBoxModelSerializer
):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambaobservedgroup-detail"
    )
    secret_safe_fields = ("name", "sid", "members")

    class Meta:
        model = SambaObservedGroup
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "name",
            "sid",
            "members",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaSessionSerializer(SecretSafeObservedSerializerMixin, NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambasession-detail"
    )
    secret_safe_fields = ("username", "machine", "remote_ip", "share")

    class Meta:
        model = SambaSession
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "username",
            "machine",
            "remote_ip",
            "share",
            "pid",
            "opened_at",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")


class SambaSyncRunSerializer(SecretSafeObservedSerializerMixin, NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_fileserver-api:sambasyncrun-detail"
    )
    secret_safe_fields = ("rpc_execution_ids", "error_message")

    class Meta:
        model = SambaSyncRun
        fields = (
            "id",
            "url",
            "display",
            "domain",
            "started",
            "finished",
            "status",
            "rpc_execution_ids",
            "error_message",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        read_only_fields = ("created", "last_updated")
