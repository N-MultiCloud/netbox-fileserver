import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone
from netbox.models import NetBoxModel

from .choices import (
    ACLRoleChoices,
    DeploymentStatusChoices,
    SambaDriftStateChoices,
    SambaFunctionalLevelChoices,
    SambaSyncStatusChoices,
)

__all__ = (
    "FileServerDeployment",
    "FileServerEnrollmentToken",
    "SambaDomain",
    "NextcloudInstance",
    "FileShare",
    "DomainGroup",
    "SambaServerState",
    "SambaConfigFile",
    "SambaConfigSnapshot",
    "SambaObservedShare",
    "SambaObservedUser",
    "SambaObservedGroup",
    "SambaSession",
    "SambaSyncRun",
)

# DNS label / FQDN for the customer's web-drive hostname (lowercase).
_FQDN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
# AD realm, e.g. EMPRESA.INTERNO (uppercase, dotted).
_REALM_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9]([A-Z0-9-]{0,61}[A-Z0-9])?(\.[A-Z0-9]([A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    message="Realm must be an uppercase dotted AD realm, e.g. EMPRESA.INTERNO.",
)
# NetBIOS short domain name — 1-15 chars, uppercase, no leading/trailing hyphen.
_NETBIOS_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9]([A-Z0-9-]{0,13}[A-Z0-9])?$",
    message="NetBIOS name must be 1-15 uppercase alphanumeric/hyphen chars.",
)
# SMB share name — no path separators or reserved characters.
_SHARE_NAME_INVALID = set('/\\:*?"<>|')
DEFAULT_ENROLLMENT_TOKEN_TTL = timedelta(hours=24)
ENROLLMENT_TOKEN_BYTES = 32
_DEPLOYMENT_APPROVAL_STATUSES = {
    DeploymentStatusChoices.STATUS_PLANNED,
    DeploymentStatusChoices.STATUS_ACTIVE,
}
_ALLOW_APPROVAL_STATUS_WRITE_ATTR = "_fileserver_allow_approval_status_write"
_ALLOW_RECONCILER_STATUS_WRITE_ATTR = "_fileserver_allow_reconciler_status_write"
_REDACTED_VALUES = {"", "***", "<redacted>", "[redacted]", "redacted"}
_SECRET_FIELD_NAMES = {
    "access key",
    "api key",
    "credential",
    "lm hash",
    "nt hash",
    "password",
    "passwd",
    "private key",
    "secret",
    "token",
}
_PRIVATE_KEY_MARKER_RE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE)
_CREDENTIAL_URL_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@", re.IGNORECASE)


def _token_hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _normalized_sensitive_name(value: object) -> str:
    return re.sub(r"[_\s-]+", " ", str(value).strip().lower())


def _is_sensitive_name(value: object) -> bool:
    name = _normalized_sensitive_name(value)
    return name in _SECRET_FIELD_NAMES or any(
        name.endswith(f" {suffix}") for suffix in _SECRET_FIELD_NAMES
    )


def _is_redacted(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return normalized in _REDACTED_VALUES or (
        len(normalized) >= 3 and set(normalized) == {"*"}
    )


def validate_no_secret_material(value: object, *, field_name: str) -> None:
    """Reject credential-bearing structured data or text before persistence."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if _is_sensitive_name(key) and not _is_redacted(nested_value):
                raise ValidationError(
                    {field_name: f"Secret-bearing key {key!r} must be removed or redacted."}
                )
            validate_no_secret_material(nested_value, field_name=field_name)
        return
    if isinstance(value, (list, tuple, set)):
        for nested_value in value:
            validate_no_secret_material(nested_value, field_name=field_name)
        return
    if not isinstance(value, str) or _is_redacted(value):
        return
    if _PRIVATE_KEY_MARKER_RE.search(value) or _CREDENTIAL_URL_RE.search(value):
        raise ValidationError({field_name: "Private keys and inline credentials are not permitted."})
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        separator = "=" if "=" in stripped else ":" if ":" in stripped else None
        if separator is None:
            continue
        key, candidate = stripped.split(separator, 1)
        if _is_sensitive_name(key) and not _is_redacted(candidate):
            raise ValidationError(
                {field_name: f"Secret-bearing assignment {key.strip()!r} is not permitted."}
            )


class FileServerDeployment(NetBoxModel):
    """One sold File Server product instance = one customer environment.

    Desired state only. The NMS file-server backend (``backend``) reconciles
    Proxmox/Samba/Nextcloud to match this row and writes the observed
    ``status`` back. NetBox never holds runtime secrets — ``secret_ref`` is a
    pointer (e.g. a Vault path), never ciphertext.
    """

    tenant = models.OneToOneField(
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="fileserver_deployment",
        help_text="Customer tenant this file-server environment belongs to.",
    )
    status = models.CharField(
        max_length=30,
        choices=DeploymentStatusChoices,
        default=DeploymentStatusChoices.STATUS_PLANNED,
    )
    backend = models.ForeignKey(
        to="netbox_nms.NMSBackend",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fileserver_deployments",
        verbose_name="Reconciler backend",
        help_text="NMS backend that reconciles this deployment.",
    )
    vlan = models.ForeignKey(
        to="ipam.VLAN",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="VLAN",
        help_text="Dedicated per-tenant VLAN (allocated from a NetBox VLAN group).",
    )
    prefix = models.ForeignKey(
        to="ipam.Prefix",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="IP prefix the DC/Nextcloud addresses are allocated from.",
    )
    plan_gb = models.PositiveIntegerField(
        default=100,
        verbose_name="Plan storage (GB)",
    )
    plan_users = models.PositiveIntegerField(default=10)
    fqdn = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="FQDN",
        help_text="Public web-drive hostname, e.g. tenant.drive.example.net.",
    )
    secret_ref = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Secret reference",
        help_text="Pointer to the secret backend (e.g. a Vault path). Never the secret itself.",
    )
    description = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("fqdn",)
        verbose_name = "File Server Deployment"
        verbose_name_plural = "File Server Deployments"

    def __str__(self) -> str:
        return self.fqdn or f"deployment-{self.pk}"

    def get_status_color(self) -> str | None:
        return DeploymentStatusChoices.colors.get(self.status)

    def approve(
        self,
        *,
        status: str = DeploymentStatusChoices.STATUS_PLANNED,
    ) -> None:
        """Approve a pending deployment for reconciliation."""
        if self.status != DeploymentStatusChoices.STATUS_PENDING_APPROVAL:
            raise ValidationError(
                {"status": "Only pending-approval deployments can be approved."}
            )
        if status not in _DEPLOYMENT_APPROVAL_STATUSES:
            raise ValidationError(
                {"status": "Approved deployments must transition to planned or active."}
            )
        self.status = status
        setattr(self, _ALLOW_APPROVAL_STATUS_WRITE_ATTR, True)
        try:
            self.full_clean()
            self.save(update_fields=("status", "last_updated"))
        finally:
            if hasattr(self, _ALLOW_APPROVAL_STATUS_WRITE_ATTR):
                delattr(self, _ALLOW_APPROVAL_STATUS_WRITE_ATTR)

    def allow_reconciler_status_write(self) -> None:
        """Permit one API save from the reconciler service account."""
        setattr(self, _ALLOW_RECONCILER_STATUS_WRITE_ATTR, True)

    def clean(self) -> None:
        super().clean()
        if self.fqdn:
            self.fqdn = self.fqdn.strip().lower()
            if not _FQDN_RE.match(self.fqdn):
                raise ValidationError({"fqdn": "Enter a valid lowercase FQDN, e.g. tenant.drive.example.net."})
        self._validate_status_transition()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "status" in update_fields:
            self._validate_status_transition()
        return super().save(*args, **kwargs)

    def _validate_status_transition(self) -> None:
        if not self.pk:
            return
        previous_status = (
            type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
        )
        if previous_status is None or previous_status == self.status:
            return
        if getattr(self, _ALLOW_RECONCILER_STATUS_WRITE_ATTR, False):
            return
        if getattr(self, _ALLOW_APPROVAL_STATUS_WRITE_ATTR, False):
            if (
                previous_status == DeploymentStatusChoices.STATUS_PENDING_APPROVAL
                and self.status in _DEPLOYMENT_APPROVAL_STATUSES
            ):
                return
            raise ValidationError(
                {"status": "Only pending-approval deployments can be approved."}
            )
        raise ValidationError(
            {
                "status": (
                    "Deployment status may only be changed through the approve "
                    "action or by the reconciler service account."
                )
            }
        )


class FileServerEnrollmentToken(NetBoxModel):
    """One-time tenant-scoped enrollment token.

    Only ``token_hash`` is persisted. The plaintext token is generated by
    ``mint_token()`` and returned once to the caller that created it.
    """

    token_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="SHA-256 hash of the enrollment token. Plaintext is never stored.",
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="fileserver_enrollment_tokens",
        help_text="Customer tenant this enrollment token is scoped to.",
    )
    target_deployment = models.ForeignKey(
        to="netbox_fileserver.FileServerDeployment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollment_tokens",
        help_text="Optional pre-created deployment this token should enroll.",
    )
    expires_at = models.DateTimeField(help_text="UTC expiry for this one-time token.")
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp set when the reconciler consumes the token.",
    )

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("-created",)
        verbose_name = "File Server Enrollment Token"
        verbose_name_plural = "File Server Enrollment Tokens"

    def __str__(self) -> str:
        return f"{self.tenant} enrollment token"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @staticmethod
    def hash_plaintext(plaintext: str) -> str:
        return _token_hash(plaintext)

    @staticmethod
    def generate_plaintext() -> str:
        return secrets.token_urlsafe(ENROLLMENT_TOKEN_BYTES)

    @staticmethod
    def default_expires_at():
        return timezone.now() + DEFAULT_ENROLLMENT_TOKEN_TTL

    @classmethod
    def mint_token(
        cls,
        *,
        tenant,
        target_deployment=None,
        expires_at=None,
        ttl: timedelta = DEFAULT_ENROLLMENT_TOKEN_TTL,
    ):
        """Create a token row and return ``(instance, plaintext)`` once."""
        plaintext = cls.generate_plaintext()
        instance = cls(
            token_hash=cls.hash_plaintext(plaintext),
            tenant=tenant,
            target_deployment=target_deployment,
            expires_at=expires_at or timezone.now() + ttl,
        )
        instance.full_clean()
        instance.save()
        instance._plaintext_token = plaintext
        return instance, plaintext

    @classmethod
    def get_valid_for_plaintext(cls, plaintext: str):
        token = (plaintext or "").strip()
        if not token:
            raise ValidationError({"token": "Enrollment token is required."})
        hashed = cls.hash_plaintext(token)
        instance = (
            cls.objects.select_related("tenant", "target_deployment")
            .filter(token_hash=hashed)
            .first()
        )
        if instance is None or not hmac.compare_digest(instance.token_hash, hashed):
            raise ValidationError({"token": "Enrollment token is invalid."})
        instance.validate_available()
        return instance

    @classmethod
    def consume_plaintext(cls, plaintext: str):
        token = (plaintext or "").strip()
        if not token:
            raise ValidationError({"token": "Enrollment token is required."})
        hashed = cls.hash_plaintext(token)
        with transaction.atomic():
            # Lock only the token row (`of=("self",)`): `target_deployment` is a
            # nullable FK, so select_related() adds a LEFT OUTER JOIN, and Postgres
            # cannot apply FOR UPDATE to the nullable side of an outer join.
            instance = (
                cls.objects.select_for_update(of=("self",))
                .select_related("tenant", "target_deployment")
                .filter(token_hash=hashed)
                .first()
            )
            if instance is None or not hmac.compare_digest(instance.token_hash, hashed):
                raise ValidationError({"token": "Enrollment token is invalid."})
            instance.validate_available()
            instance.used_at = timezone.now()
            instance.save(update_fields=("used_at", "last_updated"))
        return instance

    def validate_available(self) -> None:
        if self.used_at is not None:
            raise ValidationError({"token": "Enrollment token has already been used."})
        if self.expires_at <= timezone.now():
            raise ValidationError({"token": "Enrollment token has expired."})

    def clean(self) -> None:
        super().clean()
        if self.token_hash:
            self.token_hash = self.token_hash.strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", self.token_hash):
                raise ValidationError({"token_hash": "Token hash must be a SHA-256 hex digest."})
        if (
            self.target_deployment_id
            and self.tenant_id
            and self.target_deployment.tenant_id != self.tenant_id
        ):
            raise ValidationError(
                {
                    "target_deployment": (
                        "Target deployment must belong to the same tenant as the token."
                    )
                }
            )


class SambaDomain(NetBoxModel):
    """The Samba AD/DC backing a deployment. AD remains authoritative for
    identities/passwords (runtime state); this row models the infrastructure."""

    deployment = models.OneToOneField(
        to="netbox_fileserver.FileServerDeployment",
        on_delete=models.CASCADE,
        related_name="samba_domain",
    )
    realm = models.CharField(
        max_length=255,
        unique=True,
        validators=[_REALM_VALIDATOR],
        help_text="AD realm, e.g. EMPRESA.INTERNO.",
    )
    netbios_name = models.CharField(
        max_length=15,
        unique=True,
        validators=[_NETBIOS_VALIDATOR],
        verbose_name="NetBIOS name",
    )
    dc_vm = models.ForeignKey(
        to="virtualization.VirtualMachine",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="DC VM",
        help_text="Domain-controller VM/container.",
    )
    dc_ip = models.ForeignKey(
        to="ipam.IPAddress",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="DC IP",
    )
    ldaps_cert_expiry = models.DateField(
        null=True,
        blank=True,
        verbose_name="LDAPS cert expiry",
        help_text="Observed LDAPS certificate expiry (written back by the reconciler).",
    )
    functional_level = models.CharField(
        max_length=20,
        choices=SambaFunctionalLevelChoices,
        default=SambaFunctionalLevelChoices.LEVEL_2008_R2,
    )
    status = models.CharField(
        max_length=30,
        choices=DeploymentStatusChoices,
        default=DeploymentStatusChoices.STATUS_PLANNED,
    )

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("realm",)
        verbose_name = "Samba Domain"

    def __str__(self) -> str:
        return self.realm

    def get_status_color(self) -> str | None:
        return DeploymentStatusChoices.colors.get(self.status)

    def clean(self) -> None:
        super().clean()
        if self.realm:
            self.realm = self.realm.strip().upper()
        if self.netbios_name:
            self.netbios_name = self.netbios_name.strip().upper()


class NextcloudInstance(NetBoxModel):
    """The Nextcloud (Web Drive) instance backing a deployment."""

    deployment = models.OneToOneField(
        to="netbox_fileserver.FileServerDeployment",
        on_delete=models.CASCADE,
        related_name="nextcloud_instance",
    )
    vm = models.ForeignKey(
        to="virtualization.VirtualMachine",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="VM",
    )
    ip = models.ForeignKey(
        to="ipam.IPAddress",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="IP",
    )
    version = models.CharField(
        max_length=20,
        blank=True,
        help_text="Observed Nextcloud version (written back by the reconciler).",
    )
    ldap_config_id = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="LDAP config id",
        help_text="Nextcloud LDAP configuration id, e.g. s01 (written back by the reconciler).",
    )
    status = models.CharField(
        max_length=30,
        choices=DeploymentStatusChoices,
        default=DeploymentStatusChoices.STATUS_PLANNED,
    )

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("deployment",)
        verbose_name = "Nextcloud Instance"

    def __str__(self) -> str:
        return f"Nextcloud ({self.deployment})"

    def get_status_color(self) -> str | None:
        return DeploymentStatusChoices.colors.get(self.status)


class FileShare(NetBoxModel):
    """The object that ties both worlds together: one share, two access paths.

    One row describes the Samba share (path + ACL) AND its Nextcloud
    external-storage mount (+ the notify daemon's observed health). Reconciling
    one row configures both systems consistently.
    """

    deployment = models.ForeignKey(
        to="netbox_fileserver.FileServerDeployment",
        on_delete=models.CASCADE,
        related_name="shares",
    )
    name = models.CharField(max_length=80, help_text="SMB share name.")
    path = models.CharField(
        max_length=255,
        help_text="On-disk share path, e.g. /srv/shares/Departamentos.",
    )
    description = models.CharField(max_length=200, blank=True)
    # Samba side
    smb_enabled = models.BooleanField(default=True, verbose_name="SMB enabled")
    acl_spec = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ACL spec",
        help_text='List of {"group": "<DomainGroup>", "role": "ro|rw|full|deny"}.',
    )
    # Samba VFS feature toggles (rendered into the share's `vfs objects` stack).
    snapshots_enabled = models.BooleanField(
        default=True,
        verbose_name="Snapshots (Previous Versions)",
        help_text="Expose VSS/Previous Versions via the Samba vfs_shadow_copy2 module.",
    )
    recycle_enabled = models.BooleanField(
        default=True,
        verbose_name="Recycle bin",
        help_text="Keep deleted files in a recycle bin via the Samba vfs_recycle module.",
    )
    # Nextcloud side
    nc_mount_enabled = models.BooleanField(default=True, verbose_name="Nextcloud mount enabled")
    nc_mount_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Nextcloud mount id",
        help_text="files_external mount id (written back by the reconciler).",
    )
    nc_mount_point = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Nextcloud mount point",
        help_text="Mount point inside Nextcloud, e.g. /Arquivos/Departamentos.",
    )
    notify_active = models.BooleanField(
        default=False,
        verbose_name="Notify active",
        help_text="Observed state of the files_external:notify daemon.",
    )
    status = models.CharField(
        max_length=30,
        choices=DeploymentStatusChoices,
        default=DeploymentStatusChoices.STATUS_PLANNED,
    )

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("deployment", "name")
        unique_together = (("deployment", "name"),)
        verbose_name = "File Share"

    def __str__(self) -> str:
        return self.name

    def get_status_color(self) -> str | None:
        return DeploymentStatusChoices.colors.get(self.status)

    def clean(self) -> None:
        super().clean()
        # SMB share name rules.
        if self.name:
            self.name = self.name.strip()
            bad = _SHARE_NAME_INVALID.intersection(self.name)
            if bad:
                raise ValidationError(
                    {"name": f"Share name may not contain: {' '.join(sorted(bad))}"}
                )
        # acl_spec structure + group/role validation.
        if self.acl_spec in (None, ""):
            self.acl_spec = []
        if not isinstance(self.acl_spec, list):
            raise ValidationError({"acl_spec": "ACL spec must be a list of {group, role} objects."})

        valid_roles = {c[0] for c in ACLRoleChoices.CHOICES}
        known_groups = self._known_domain_group_names()
        for idx, entry in enumerate(self.acl_spec):
            if not isinstance(entry, dict):
                raise ValidationError({"acl_spec": f"Entry {idx} must be an object with group and role."})
            group = entry.get("group")
            role = entry.get("role")
            if not group or not role:
                raise ValidationError({"acl_spec": f"Entry {idx} must set both group and role."})
            if role not in valid_roles:
                raise ValidationError(
                    {"acl_spec": f"Entry {idx} role '{role}' must be one of {sorted(valid_roles)}."}
                )
            # Only enforce group existence once the domain and its groups exist.
            if known_groups is not None and group not in known_groups:
                raise ValidationError(
                    {"acl_spec": f"Entry {idx} references unknown AD group '{group}'."}
                )

    def _known_domain_group_names(self) -> set[str] | None:
        """Return the set of AD group names for this deployment's domain, or
        None when the domain (or its group inventory) is not yet modeled."""
        deployment_id = self.deployment_id
        if not deployment_id:
            return None
        domain = SambaDomain.objects.filter(deployment_id=deployment_id).first()
        if domain is None:
            return None
        names = set(domain.groups.values_list("name", flat=True))
        return names or None


class DomainGroup(NetBoxModel):
    """AD group referenced by share ACLs — modeled so ``acl_spec`` validates
    against real groups. Desired end users are NOT modeled; passwords/user churn
    stay in AD (runtime state)."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="groups",
    )
    name = models.CharField(max_length=64, help_text="AD group name, e.g. Diretoria.")
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "name")
        unique_together = (("domain", "name"),)
        verbose_name = "Domain Group"

    def __str__(self) -> str:
        return self.name


class SambaServerState(NetBoxModel):
    """Last observed Samba version, service health, and config validation."""

    domain = models.OneToOneField(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="server_state",
    )
    version = models.CharField(max_length=100, blank=True)
    smbd_active_state = models.CharField(max_length=30, blank=True)
    smbd_sub_state = models.CharField(max_length=30, blank=True)
    smbd_unit_file_state = models.CharField(max_length=30, blank=True)
    nmbd_active_state = models.CharField(max_length=30, blank=True)
    nmbd_sub_state = models.CharField(max_length=30, blank=True)
    nmbd_unit_file_state = models.CharField(max_length=30, blank=True)
    winbind_active_state = models.CharField(max_length=30, blank=True)
    winbind_sub_state = models.CharField(max_length=30, blank=True)
    winbind_unit_file_state = models.CharField(max_length=30, blank=True)
    samba_ad_dc_active_state = models.CharField(max_length=30, blank=True)
    samba_ad_dc_sub_state = models.CharField(max_length=30, blank=True)
    samba_ad_dc_unit_file_state = models.CharField(max_length=30, blank=True)
    config_sha256 = models.CharField(max_length=64, blank=True)
    testparm_ok = models.BooleanField(default=False)
    observed_at = models.DateTimeField()

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain",)
        verbose_name = "Samba Server State"

    def __str__(self) -> str:
        return f"Samba state ({self.domain})"


class SambaConfigFile(NetBoxModel):
    """Last fetched content and file metadata for one Samba config file."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="config_files",
    )
    path = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    mtime = models.DateTimeField()
    is_primary = models.BooleanField(default=False)
    fetched_at = models.DateTimeField()

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "path")
        unique_together = (("domain", "path"),)
        verbose_name = "Samba Config File"

    def __str__(self) -> str:
        return self.path

    def clean(self) -> None:
        super().clean()
        validate_no_secret_material(self.content, field_name="content")


class SambaConfigSnapshot(NetBoxModel):
    """Point-in-time archive of a Samba configuration file set."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="config_snapshots",
    )
    snapshot_id = models.CharField(max_length=128)
    content = models.JSONField(default=dict)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "-created")
        unique_together = (("domain", "snapshot_id"),)
        verbose_name = "Samba Config Snapshot"

    def __str__(self) -> str:
        return self.snapshot_id

    def clean(self) -> None:
        super().clean()
        validate_no_secret_material(self.content, field_name="content")


class SambaObservedShare(NetBoxModel):
    """Effective Samba share state reported by the reconciler."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="observed_shares",
    )
    name = models.CharField(max_length=80)
    path = models.CharField(max_length=255, blank=True)
    raw_params = models.JSONField(default=dict, blank=True)
    browseable = models.BooleanField(default=True)
    read_only = models.BooleanField(default=True)
    guest_ok = models.BooleanField(default=False)
    drift_state = models.CharField(
        max_length=30,
        choices=SambaDriftStateChoices,
        default=SambaDriftStateChoices.STATE_UNMANAGED,
    )

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "name")
        unique_together = (("domain", "name"),)
        verbose_name = "Samba Observed Share"

    def __str__(self) -> str:
        return self.name

    def get_drift_state_color(self) -> str | None:
        return SambaDriftStateChoices.colors.get(self.drift_state)

    def clean(self) -> None:
        super().clean()
        validate_no_secret_material(self.raw_params, field_name="raw_params")


class SambaObservedUser(NetBoxModel):
    """Non-secret Samba directory user metadata observed for operations."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="observed_users",
    )
    username = models.CharField(max_length=255)
    sid = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(default=True)
    last_logon = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "username")
        unique_together = (("domain", "username"),)
        verbose_name = "Samba Observed User"

    def __str__(self) -> str:
        return self.username


class SambaObservedGroup(NetBoxModel):
    """Samba directory group membership observed for operations."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="observed_groups",
    )
    name = models.CharField(max_length=255)
    sid = models.CharField(max_length=255, blank=True)
    members = models.JSONField(default=list, blank=True)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "name")
        unique_together = (("domain", "name"),)
        verbose_name = "Samba Observed Group"

    def __str__(self) -> str:
        return self.name


class SambaSession(NetBoxModel):
    """One live connection reported by ``smbstatus``."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    username = models.CharField(max_length=255, blank=True)
    machine = models.CharField(max_length=255, blank=True)
    remote_ip = models.GenericIPAddressField(null=True, blank=True)
    share = models.CharField(max_length=80, blank=True)
    pid = models.PositiveBigIntegerField()
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("domain", "username", "machine", "share", "pid")
        verbose_name = "Samba Session"

    def __str__(self) -> str:
        return f"{self.username or 'anonymous'} on {self.share or self.machine}"


class SambaSyncRun(NetBoxModel):
    """Audit record for one reconciler collection and fold operation."""

    domain = models.ForeignKey(
        to="netbox_fileserver.SambaDomain",
        on_delete=models.CASCADE,
        related_name="sync_runs",
    )
    started = models.DateTimeField(default=timezone.now)
    finished = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=SambaSyncStatusChoices,
        default=SambaSyncStatusChoices.STATUS_RUNNING,
    )
    rpc_execution_ids = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = "netbox_fileserver"
        ordering = ("-started",)
        verbose_name = "Samba Sync Run"

    def __str__(self) -> str:
        return f"{self.domain} sync {self.pk or 'new'}"

    def get_status_color(self) -> str | None:
        return SambaSyncStatusChoices.colors.get(self.status)

    def clean(self) -> None:
        super().clean()
        validate_no_secret_material(self.error_message, field_name="error_message")
