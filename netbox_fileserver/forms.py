from django import forms
from ipam.models import VLAN, IPAddress, Prefix
from netbox.forms import (
    NetBoxModelBulkEditForm,
    NetBoxModelFilterSetForm,
    NetBoxModelForm,
)

# netbox-nms is a required_plugins dependency, so it is always importable when
# NetBox loads this plugin; a direct import keeps the form querysets correct.
from netbox_nms.models import NMSBackend
from tenancy.models import Tenant
from utilities.forms import add_blank_choice
from utilities.forms.fields import DynamicModelChoiceField, JSONField
from virtualization.models import VirtualMachine

from .choices import DeploymentStatusChoices, SambaFunctionalLevelChoices
from .models import (
    DomainGroup,
    FileServerDeployment,
    FileServerEnrollmentToken,
    FileShare,
    NextcloudInstance,
    SambaDomain,
)

# ─────────────────────────── ModelForms ───────────────────────────


class FileServerDeploymentForm(NetBoxModelForm):
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all())
    backend = DynamicModelChoiceField(
        queryset=NMSBackend.objects.all(),
        required=False,
        label="Reconciler backend",
    )
    vlan = DynamicModelChoiceField(queryset=VLAN.objects.all(), required=False)
    prefix = DynamicModelChoiceField(queryset=Prefix.objects.all(), required=False)

    class Meta:
        model = FileServerDeployment
        fields = (
            "tenant",
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
        )


class FileServerEnrollmentTokenForm(NetBoxModelForm):
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all())
    target_deployment = DynamicModelChoiceField(
        queryset=FileServerDeployment.objects.all(), required=False
    )
    token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Plaintext token to hash at save time. Use the REST API to mint and "
            "receive a generated token once."
        ),
    )

    class Meta:
        model = FileServerEnrollmentToken
        fields = (
            "tenant",
            "target_deployment",
            "expires_at",
            "tags",
        )

    def clean(self):
        data = super().clean()
        token = (data.get("token") or "").strip()
        if not self.instance.pk and not token:
            raise forms.ValidationError(
                "Supply a plaintext token here or create the token through the REST API."
            )
        if token:
            self.instance.token_hash = FileServerEnrollmentToken.hash_plaintext(token)
        return data


class SambaDomainForm(NetBoxModelForm):
    deployment = DynamicModelChoiceField(queryset=FileServerDeployment.objects.all())
    dc_vm = DynamicModelChoiceField(
        queryset=VirtualMachine.objects.all(), required=False, label="DC VM"
    )
    dc_ip = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(), required=False, label="DC IP"
    )

    class Meta:
        model = SambaDomain
        fields = (
            "deployment",
            "realm",
            "netbios_name",
            "dc_vm",
            "dc_ip",
            "functional_level",
            "status",
            "tags",
        )


class NextcloudInstanceForm(NetBoxModelForm):
    deployment = DynamicModelChoiceField(queryset=FileServerDeployment.objects.all())
    vm = DynamicModelChoiceField(queryset=VirtualMachine.objects.all(), required=False)
    ip = DynamicModelChoiceField(queryset=IPAddress.objects.all(), required=False)

    class Meta:
        model = NextcloudInstance
        fields = (
            "deployment",
            "vm",
            "ip",
            "status",
            "tags",
        )


class FileShareForm(NetBoxModelForm):
    deployment = DynamicModelChoiceField(queryset=FileServerDeployment.objects.all())
    acl_spec = JSONField(
        required=False,
        label="ACL spec",
        help_text='List of {"group": "<DomainGroup>", "role": "ro|rw|full|deny"}.',
    )

    class Meta:
        model = FileShare
        fields = (
            "deployment",
            "name",
            "path",
            "description",
            "smb_enabled",
            "acl_spec",
            "snapshots_enabled",
            "recycle_enabled",
            "nc_mount_enabled",
            "nc_mount_point",
            "status",
            "tags",
        )


class DomainGroupForm(NetBoxModelForm):
    domain = DynamicModelChoiceField(queryset=SambaDomain.objects.all())

    class Meta:
        model = DomainGroup
        fields = ("domain", "name", "description", "tags")


# ─────────────────────────── Bulk-edit forms ───────────────────────────
# Observed (reconciler-written) fields are intentionally excluded — operators
# never bulk-set version/nc_mount_id/notify_active/ldaps_cert_expiry.


class FileServerDeploymentBulkEditForm(NetBoxModelBulkEditForm):
    model = FileServerDeployment

    plan_gb = forms.IntegerField(required=False, label="Plan storage (GB)")
    plan_users = forms.IntegerField(required=False)
    description = forms.CharField(max_length=255, required=False)
    comments = forms.CharField(required=False, widget=forms.Textarea)

    nullable_fields = ("description", "comments")


class FileServerEnrollmentTokenBulkEditForm(NetBoxModelBulkEditForm):
    model = FileServerEnrollmentToken

    expires_at = forms.DateTimeField(required=False)

    nullable_fields = ()


class SambaDomainBulkEditForm(NetBoxModelBulkEditForm):
    model = SambaDomain

    status = forms.ChoiceField(
        choices=add_blank_choice(DeploymentStatusChoices), required=False
    )
    functional_level = forms.ChoiceField(
        choices=add_blank_choice(SambaFunctionalLevelChoices), required=False
    )

    nullable_fields = ()


class NextcloudInstanceBulkEditForm(NetBoxModelBulkEditForm):
    model = NextcloudInstance

    status = forms.ChoiceField(
        choices=add_blank_choice(DeploymentStatusChoices), required=False
    )

    nullable_fields = ()


class FileShareBulkEditForm(NetBoxModelBulkEditForm):
    model = FileShare

    status = forms.ChoiceField(
        choices=add_blank_choice(DeploymentStatusChoices), required=False
    )
    description = forms.CharField(max_length=200, required=False)

    nullable_fields = ("description",)


class DomainGroupBulkEditForm(NetBoxModelBulkEditForm):
    model = DomainGroup

    description = forms.CharField(max_length=200, required=False)

    nullable_fields = ("description",)


# ─────────────────────────── Filter forms ───────────────────────────


class FileServerDeploymentFilterForm(NetBoxModelFilterSetForm):
    model = FileServerDeployment

    fqdn = forms.CharField(required=False)
    status = forms.MultipleChoiceField(choices=DeploymentStatusChoices, required=False)
    tenant_id = DynamicModelChoiceField(
        queryset=Tenant.objects.all(), required=False, label="Tenant"
    )


class FileServerEnrollmentTokenFilterForm(NetBoxModelFilterSetForm):
    model = FileServerEnrollmentToken

    tenant_id = DynamicModelChoiceField(
        queryset=Tenant.objects.all(), required=False, label="Tenant"
    )
    target_deployment_id = DynamicModelChoiceField(
        queryset=FileServerDeployment.objects.all(),
        required=False,
        label="Target deployment",
    )
    used = forms.NullBooleanField(required=False)


class SambaDomainFilterForm(NetBoxModelFilterSetForm):
    model = SambaDomain

    realm = forms.CharField(required=False)
    netbios_name = forms.CharField(required=False, label="NetBIOS name")
    status = forms.MultipleChoiceField(choices=DeploymentStatusChoices, required=False)


class NextcloudInstanceFilterForm(NetBoxModelFilterSetForm):
    model = NextcloudInstance

    version = forms.CharField(required=False)
    status = forms.MultipleChoiceField(choices=DeploymentStatusChoices, required=False)


class FileShareFilterForm(NetBoxModelFilterSetForm):
    model = FileShare

    name = forms.CharField(required=False)
    path = forms.CharField(required=False)
    status = forms.MultipleChoiceField(choices=DeploymentStatusChoices, required=False)
    deployment_id = DynamicModelChoiceField(
        queryset=FileServerDeployment.objects.all(), required=False, label="Deployment"
    )


class DomainGroupFilterForm(NetBoxModelFilterSetForm):
    model = DomainGroup

    name = forms.CharField(required=False)
    domain_id = DynamicModelChoiceField(
        queryset=SambaDomain.objects.all(), required=False, label="Domain"
    )
