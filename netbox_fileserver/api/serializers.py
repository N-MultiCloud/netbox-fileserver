from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ..models import (
    DomainGroup,
    FileServerDeployment,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)


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
        read_only_fields = ("created", "last_updated")


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
