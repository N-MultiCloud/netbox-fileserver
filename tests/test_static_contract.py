"""Import-free static-contract tests.

These assert the plugin's structural invariants by reading source text, so they
run in CI without a NetBox/Django environment or a database.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "netbox_fileserver"

MODEL_FILES = (
    "__init__.py",
    "choices.py",
    "models.py",
    "filtersets.py",
    "forms.py",
    "tables.py",
    "views.py",
    "urls.py",
    "navigation.py",
    "search.py",
    "template_content.py",
    "api/serializers.py",
    "api/views.py",
    "api/urls.py",
    "graphql/types.py",
    "graphql/schema.py",
)

# NOTE: The strings below are the dangerous *patterns this test scans source
# for* — they are string literals used for detection, never executed. The test
# asserts none of them appear in the plugin's own Python sources.
FORBIDDEN_PATTERNS = (
    "eval(",
    "exec(",
    "os.system(",
    "pickle.loads(",
    "innerHTML",
    "dangerouslySetInnerHTML",
    "subprocess.",
)


def read(rel: str) -> str:
    return (PKG / rel).read_text(encoding="utf-8")


# ─────────────────────────── Plugin config ───────────────────────────


def test_plugin_config_name_and_base_url():
    src = read("__init__.py")
    assert 'name = "netbox_fileserver"' in src
    assert 'base_url = "fileserver"' in src


def test_plugin_requires_netbox_nms():
    src = read("__init__.py")
    assert 'required_plugins = ["netbox_nms"]' in src


def test_plugin_version_bounds():
    src = read("__init__.py")
    assert 'min_version = "4.5.0"' in src
    assert 'max_version = "4.6.99"' in src


# ─────────────────────────────── Models ───────────────────────────────


def test_all_six_models_present():
    src = read("models.py")
    for cls in (
        "class FileServerDeployment(NetBoxModel):",
        "class FileServerEnrollmentToken(NetBoxModel):",
        "class SambaDomain(NetBoxModel):",
        "class NextcloudInstance(NetBoxModel):",
        "class FileShare(NetBoxModel):",
        "class DomainGroup(NetBoxModel):",
    ):
        assert cls in src, cls


def test_deployment_secret_is_reference_only_not_ciphertext():
    """NetBox holds only a pointer to the secret, never the secret itself."""
    src = read("models.py")
    assert "secret_ref = models.CharField(" in src
    # The plugin must not import or use encryption helpers — no secrets at rest.
    assert "Fernet" not in src
    assert "encrypt_secret" not in src
    assert "decrypt_secret" not in src
    assert "_encrypted" not in src


def test_deployment_backend_fk_to_nmsbackend():
    src = read("models.py")
    assert 'to="netbox_nms.NMSBackend"' in src
    assert "on_delete=models.SET_NULL" in src


def test_deployment_tenant_is_protected_one_to_one():
    src = read("models.py")
    assert 'to="tenancy.Tenant"' in src
    assert "on_delete=models.PROTECT" in src
    assert 'related_name="fileserver_deployment"' in src


def test_enrollment_token_is_hash_only_one_time_and_tenant_scoped():
    src = read("models.py")
    assert "class FileServerEnrollmentToken(NetBoxModel):" in src
    assert "token_hash = models.CharField(" in src
    assert "hashlib.sha256" in src
    assert "hmac.compare_digest" in src
    assert "secrets.token_urlsafe" in src
    assert "used_at = models.DateTimeField" in src
    assert "expires_at = models.DateTimeField" in src
    assert 'to="tenancy.Tenant"' in src
    assert 'to="netbox_fileserver.FileServerDeployment"' in src
    # Row-scoped lock: `of=("self",)` locks only the token row (target_deployment
    # is a nullable FK → LEFT JOIN → Postgres rejects FOR UPDATE on the null side).
    assert 'select_for_update(of=("self",))' in src
    assert "def mint_token(" in src
    assert "def consume_plaintext(" in src
    assert "token = models." not in src


def test_fileshare_is_the_integration_object():
    src = read("models.py")
    assert "class FileShare(NetBoxModel):" in src
    assert "smb_enabled = models.BooleanField" in src
    assert "acl_spec = models.JSONField" in src
    assert "nc_mount_enabled = models.BooleanField" in src
    assert "notify_active = models.BooleanField" in src
    assert 'unique_together = (("deployment", "name"),)' in src


def test_fileshare_models_samba_vfs_features():
    """A share carries the real per-share Samba VFS product features
    (Previous Versions / recycle bin), not just path + ACL."""
    src = read("models.py")
    assert "snapshots_enabled = models.BooleanField" in src
    assert "recycle_enabled = models.BooleanField" in src
    assert "vfs_shadow_copy2" in src
    assert "vfs_recycle" in src


def test_fileshare_clean_validates_acl_spec_against_groups():
    src = read("models.py")
    assert "def clean(self) -> None:" in src
    assert "_known_domain_group_names" in src
    assert "references unknown AD group" in src


def test_domain_group_scoped_to_domain():
    src = read("models.py")
    assert "class DomainGroup(NetBoxModel):" in src
    assert 'to="netbox_fileserver.SambaDomain"' in src
    assert 'unique_together = (("domain", "name"),)' in src


def test_observed_fields_present():
    """Reconciler-written observed fields exist for drift visibility."""
    src = read("models.py")
    for field in ("ldaps_cert_expiry", "nc_mount_id", "notify_active", "version"):
        assert field in src, field


# ─────────────────────────────── Choices ──────────────────────────────


def test_deployment_status_lifecycle():
    src = read("choices.py")
    for value in (
        "pending_approval",
        "planned",
        "provisioning",
        "active",
        "failed",
        "decommissioning",
    ):
        assert f'"{value}"' in src, value


def test_acl_role_choices():
    src = read("choices.py")
    assert "class ACLRoleChoices(ChoiceSet):" in src
    for value in ("ro", "rw", "full", "deny"):
        assert f'"{value}"' in src, value


# ────────────────────────────── REST API ──────────────────────────────


def test_api_router_registers_all_collections():
    src = read("api/urls.py")
    assert "router = NetBoxRouter()" in src
    for path in (
        "deployments",
        "enrollment-tokens",
        "samba-domains",
        "nextcloud-instances",
        "shares",
        "domain-groups",
    ):
        assert f'router.register("{path}"' in src, path


def test_api_serializers_expose_plaintext_only_on_mint_or_agent_submit():
    src = read("api/serializers.py")
    # secret_ref is a pointer. Enrollment plaintext is never a model field; it
    # appears only as a read-only mint response or write-only agent input. The
    # stored hash is written internally but never serialized.
    assert "_encrypted" not in src
    assert "token = serializers.CharField(read_only=True)" in src
    assert "token = serializers.CharField(write_only=True" in src
    assert '"token_hash",' not in src
    assert 'data["token_hash"] = FileServerEnrollmentToken.hash_plaintext' in src
    assert '"token",' in src
    assert '"used_at",' in src


def test_api_actions_cover_enrollment_consume_and_deployment_approve():
    src = read("api/views.py")
    assert '@action(detail=True, methods=["post"], url_path="approve")' in src
    assert '@action(detail=False, methods=["post"], url_path="consume")' in src
    assert "change_fileserverenrollmenttoken" in src
    assert "Cloud Portal: {slug} :: Admins" in src
    assert 'FileServerDeployment.objects.restrict(request.user, "change")' in src
    assert "global reconciler service identity boundary" in src
    assert "FileServerAgentEnrollSerializer" in src


# ────────────────────────────── Migration ─────────────────────────────


def test_migration_declares_all_models_and_deps():
    # Quote-agnostic: the migration is makemigrations-generated (single quotes).
    src = (PKG / "migrations" / "0001_initial.py").read_text(encoding="utf-8")
    assert "initial = True" in src
    assert src.count("migrations.CreateModel") == 5
    for name in (
        "FileServerDeployment",
        "SambaDomain",
        "NextcloudInstance",
        "FileShare",
        "DomainGroup",
    ):
        assert name in src, name
    # netbox_nms provides NMSBackend (FK target); assert the dependency apps.
    assert "netbox_nms" in src
    for app in ("extras", "tenancy", "ipam", "virtualization"):
        assert app in src, app


def test_enrollment_token_migration_is_scoped_and_hash_only():
    src = (PKG / "migrations" / "0002_fileserverenrollmenttoken.py").read_text(
        encoding="utf-8"
    )
    assert src.count("migrations.CreateModel") == 1
    assert "FileServerEnrollmentToken" in src
    assert "token_hash" in src
    assert "unique=True" in src
    assert "expires_at" in src
    assert "used_at" in src
    assert "target_deployment" in src
    assert "tenant" in src
    assert "plaintext" not in src


# ────────────────────────── Wiring / registration ─────────────────────


def test_navigation_registers_menu():
    src = read("navigation.py")
    assert "menu = PluginMenu(" in src
    assert 'label="File Server"' in src


def test_template_content_exposes_extensions():
    src = read("template_content.py")
    assert "template_extensions = (" in src
    # NetBox 4.x uses the plural `models` list, not singular `model` (the latter
    # silently registers the panel globally on every object detail page).
    assert 'models = ["tenancy.tenant"]' in src
    assert 'models = ["virtualization.virtualmachine"]' in src


def test_search_registers_indexes():
    src = read("search.py")
    assert src.count("@register_search") == 5
    assert "FileServerEnrollmentTokenIndex" not in src
    assert "token_hash" not in src


# ──────────────────────────────── Security ────────────────────────────


def test_no_forbidden_patterns_in_python_sources():
    for rel in MODEL_FILES:
        src = read(rel)
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in src, f"{pattern} found in {rel}"


# ─────────────────── Full CRUD surface + reconciler contract ───────────────────

# (ClassName, url/template model name, url slug)
MODELS = (
    ("FileServerDeployment", "fileserverdeployment", "deployments"),
    ("FileServerEnrollmentToken", "fileserverenrollmenttoken", "enrollment-tokens"),
    ("SambaDomain", "sambadomain", "samba-domains"),
    ("NextcloudInstance", "nextcloudinstance", "nextcloud-instances"),
    ("FileShare", "fileshare", "shares"),
    ("DomainGroup", "domaingroup", "domain-groups"),
)

# Reconciler-written (observed) fields — the external reconciler PATCHes these,
# so they must be WRITABLE in the API and ABSENT from the operator forms.
OBSERVED_FIELDS = (
    "version",
    "nc_mount_id",
    "notify_active",
    "ldaps_cert_expiry",
    "ldap_config_id",
)


def test_serializers_keep_observed_fields_writable():
    """The reconciler must be able to PATCH non-deployment observed fields, so
    those object serializers keep them writable. Deployment status has a
    reconciler-only serializer because it gates the approval state machine."""
    src = read("api/serializers.py")
    assert src.count('read_only_fields = ("created", "last_updated")') == 5
    assert 'read_only_fields = ("status", "created", "last_updated")' in src
    assert "class FileServerDeploymentReconcilerSerializer" in src
    assert "allow_reconciler_status_write" in src
    # Belt-and-suspenders: no observed field name appears on a read_only line.
    for line in src.splitlines():
        if "read_only_fields" in line:
            for field in OBSERVED_FIELDS:
                assert field not in line, f"{field} must stay writable"


def test_deployment_status_transitions_are_guarded():
    models_src = read("models.py")
    forms_src = read("forms.py")
    views_src = read("api/views.py")

    assert "def _validate_status_transition(self) -> None:" in models_src
    assert "Deployment status may only be changed through the approve" in models_src
    assert "allow_reconciler_status_write" in models_src
    assert "STATUS_PENDING_APPROVAL" in models_src
    assert "_DEPLOYMENT_APPROVAL_STATUSES" in models_src
    assert "FileServerDeploymentReconcilerSerializer" in views_src
    assert 'FILESERVER_RECONCILER_GROUP_NAME = "File Server Reconcilers"' in views_src

    deployment_form = forms_src.split("class FileServerEnrollmentTokenForm")[0]
    deployment_bulk = forms_src.split("class FileServerDeploymentBulkEditForm")[1].split(
        "class FileServerEnrollmentTokenBulkEditForm"
    )[0]
    assert '"status"' not in deployment_form
    assert "status = forms.ChoiceField" not in deployment_bulk


def test_forms_exclude_reconciler_written_fields():
    """Observed fields are reconciler-owned and must never appear as editable
    form fields (also guards against the ModelForm non-editable FieldError)."""
    src = read("forms.py")
    for field in OBSERVED_FIELDS:
        assert f'"{field}"' not in src, f"{field} must not be a form field"


def test_forms_do_not_hardcode_a_none_queryset_fallback():
    """netbox-nms is a required plugin — NMSBackend is imported directly, with no
    wrong-typed .objects.none() fallback."""
    src = read("forms.py")
    assert "from netbox_nms.models import NMSBackend" in src
    assert "FileServerDeployment.objects.none()" not in src


def test_enrollment_token_hash_is_not_exposed_by_public_surfaces():
    serializers = read("api/serializers.py")
    graphql = read("graphql/types.py")
    template = (PKG / "templates" / "netbox_fileserver" / "fileserverenrollmenttoken.html").read_text(
        encoding="utf-8"
    )
    forms_src = read("forms.py")

    assert '"token_hash",' not in serializers
    assert 'fields="__all__")\nclass FileServerEnrollmentTokenType' not in graphql
    assert '"token_hash"' not in graphql
    assert "{{ object.token_hash }}" not in template
    assert "PasswordInput(render_value=False)" in forms_src


def test_bulk_edit_is_wired_for_all_models():
    forms_src = read("forms.py")
    views_src = read("views.py")
    urls_src = read("urls.py")
    assert forms_src.count("(NetBoxModelBulkEditForm):") == 6
    assert views_src.count("(generic.BulkEditView):") == 6
    assert 'name=f"{name}_bulk_edit"' in urls_src


def test_every_model_has_the_full_plugin_surface():
    serializers = read("api/serializers.py")
    api_views = read("api/views.py")
    filtersets = read("filtersets.py")
    forms_src = read("forms.py")
    tables = read("tables.py")
    views_src = read("views.py")
    for cls, _name, _slug in MODELS:
        assert f"class {cls}Serializer(" in serializers, cls
        assert f"class {cls}ViewSet(" in api_views, cls
        assert f"class {cls}FilterSet(" in filtersets, cls
        assert f"class {cls}Form(" in forms_src, cls
        assert f"class {cls}BulkEditForm(" in forms_src, cls
        assert f"class {cls}Table(" in tables, cls
        for suffix in ("ListView", "EditView", "DeleteView", "BulkEditView", "BulkDeleteView"):
            assert f"class {cls}{suffix}(" in views_src, f"{cls}{suffix}"


def test_detail_template_exists_for_every_model():
    for _cls, name, _slug in MODELS:
        tmpl = PKG / "templates" / "netbox_fileserver" / f"{name}.html"
        assert tmpl.is_file(), f"missing detail template {name}.html"


def test_navigation_and_urls_cover_every_model():
    nav = read("navigation.py")
    urls = read("urls.py")
    for _cls, name, slug in MODELS:
        assert name in nav, f"{name} missing from navigation"
        assert name in urls, f"{name} missing from urls"
        assert f'"{slug}"' in urls, f"{slug} slug missing from urls"
