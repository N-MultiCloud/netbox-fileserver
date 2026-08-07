"""Import-free static-contract tests.

These assert the plugin's structural invariants by reading source text, so they
run in CI without a NetBox/Django environment or a database.
"""

import ast
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

FORBIDDEN_MIGRATION_DEPENDENCIES = {
    ("dcim", "0236_moduletype_component_counts"),
    ("extras", "0138_customfieldchoiceset_choice_colors"),
    ("extras", "0139_alter_customfieldchoiceset_extra_choices"),
    ("ipam", "0090_vlangroup_recompute_total_vlan_ids"),
    ("ipam", "0092_iprange_host_indexes"),
    ("tenancy", "0024_default_ordering_indexes"),
    ("virtualization", "0056_virtualmachine_render_config_permission"),
}

FORBIDDEN_MIGRATION_DEPENDENCY_PREFIXES = {
    ("virtualization", "0053_"),
    ("virtualization", "0054_"),
    ("virtualization", "0055_"),
    ("virtualization", "0056_"),
}


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
    assert 'min_version = "4.5.8"' in src
    assert 'max_version = "4.6.99"' in src


def _literal_dependency(node: ast.AST) -> tuple[str, str] | None:
    if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
        return None
    app_label, migration_name = node.elts
    if not (
        isinstance(app_label, ast.Constant)
        and isinstance(app_label.value, str)
        and isinstance(migration_name, ast.Constant)
        and isinstance(migration_name.value, str)
    ):
        return None
    return app_label.value, migration_name.value


def test_migrations_do_not_depend_on_netbox_46_only_core_nodes():
    violations: list[str] = []

    for path in sorted((PKG / "migrations").glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "dependencies"
                for target in node.targets
            ):
                continue
            if not isinstance(node.value, ast.List):
                continue
            for dependency_node in node.value.elts:
                dependency = _literal_dependency(dependency_node)
                if dependency is None:
                    continue
                app_label, migration_name = dependency
                if dependency in FORBIDDEN_MIGRATION_DEPENDENCIES:
                    violations.append(f"{path.name}: {app_label}.{migration_name}")
                for prefix_app_label, prefix in FORBIDDEN_MIGRATION_DEPENDENCY_PREFIXES:
                    if app_label == prefix_app_label and migration_name.startswith(prefix):
                        violations.append(f"{path.name}: {app_label}.{migration_name}")

    assert not violations, (
        "Plugin migrations must target NetBox core migration nodes present in "
        f"both NetBox 4.5.8 and 4.6.x: {violations}"
    )


# ─────────────────────────────── Models ───────────────────────────────


def test_all_fourteen_models_present():
    src = read("models.py")
    for cls in (
        "class FileServerDeployment(NetBoxModel):",
        "class FileServerEnrollmentToken(NetBoxModel):",
        "class SambaDomain(NetBoxModel):",
        "class NextcloudInstance(NetBoxModel):",
        "class FileShare(NetBoxModel):",
        "class DomainGroup(NetBoxModel):",
        "class SambaServerState(NetBoxModel):",
        "class SambaConfigFile(NetBoxModel):",
        "class SambaConfigSnapshot(NetBoxModel):",
        "class SambaObservedShare(NetBoxModel):",
        "class SambaObservedUser(NetBoxModel):",
        "class SambaObservedGroup(NetBoxModel):",
        "class SambaSession(NetBoxModel):",
        "class SambaSyncRun(NetBoxModel):",
    ):
        assert cls in src, cls


def _model_field_names(class_name: str) -> set[str]:
    tree = ast.parse(read("models.py"))
    model_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    names = set()
    for node in model_class.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "models"
        ):
            names.add(target.id)
    return names


def _model_field_types(class_name: str) -> dict[str, str]:
    tree = ast.parse(read("models.py"))
    model_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    fields = {}
    for node in model_class.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "models"
        ):
            fields[target.id] = func.attr
    return fields


def _class_node(rel: str, class_name: str) -> ast.ClassDef:
    tree = ast.parse(read(rel))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )


def _literal_assignment(rel: str, name: str):
    tree = ast.parse(read(rel))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def _form_meta_fields(class_name: str) -> tuple[str, ...]:
    form_class = _class_node("forms.py", class_name)
    meta_class = next(
        node
        for node in form_class.body
        if isinstance(node, ast.ClassDef) and node.name == "Meta"
    )
    fields_assignment = next(
        node
        for node in meta_class.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "fields"
            for target in node.targets
        )
    )
    return ast.literal_eval(fields_assignment.value)


def _migration_model_field_types(path: Path) -> dict[str, dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "CreateModel":
            continue
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        model_name = ast.literal_eval(keywords["name"])
        fields = {}
        for field_node in keywords["fields"].elts:
            field_name = ast.literal_eval(field_node.elts[0])
            field_call = field_node.elts[1]
            assert isinstance(field_call, ast.Call)
            assert isinstance(field_call.func, ast.Attribute)
            fields[field_name] = field_call.func.attr
        result[model_name] = fields
    return result


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


def test_samba_observed_models_declare_exact_fields():
    for model_name, expected_fields in SAMBA_OBSERVED_MODEL_FIELDS.items():
        assert _model_field_names(model_name) == set(expected_fields), model_name


def test_samba_observed_models_cascade_from_domain_and_set_app_label():
    src = read("models.py")
    tree = ast.parse(src)
    for model_name in SAMBA_OBSERVED_MODEL_FIELDS:
        model_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == model_name
        )
        class_src = ast.get_source_segment(src, model_class)
        assert class_src is not None
        assert 'to="netbox_fileserver.SambaDomain"' in class_src, model_name
        assert "on_delete=models.CASCADE" in class_src, model_name
        assert 'app_label = "netbox_fileserver"' in class_src, model_name
    assert _model_field_types("SambaServerState")["domain"] == "OneToOneField"
    for model_name in set(SAMBA_OBSERVED_MODEL_FIELDS) - {"SambaServerState"}:
        assert _model_field_types(model_name)["domain"] == "ForeignKey"


def test_samba_observed_user_cannot_store_secret_material():
    fields = _model_field_names("SambaObservedUser")
    assert fields == {"domain", "username", "sid", "enabled", "last_logon"}
    forbidden_fragments = (
        "password",
        "passwd",
        "nt_hash",
        "lm_hash",
        "secret",
        "ciphertext",
        "credential",
        "private_key",
    )
    assert not any(
        fragment in field.lower()
        for field in fields
        for fragment in forbidden_fragments
    )


def test_observed_payloads_reject_embedded_secret_material():
    models_src = read("models.py")
    serializers_src = read("api/serializers.py")
    assert "def validate_no_secret_material(" in models_src
    assert "_PRIVATE_KEY_MARKER_RE" in models_src
    assert "_PUTTY_PRIVATE_KEY_RE" in models_src
    assert "_CREDENTIAL_URL_RE" in models_src
    assert "_AUTH_SCHEME_VALUE_RE" in models_src
    assert "_CLI_SECRET_ARGUMENT_RE" in models_src
    assert "_PASSWORD_HASH_RE" in models_src
    assert "_PWDUMP_HASH_RE" in models_src
    assert "class SecretSafeObservedSerializerMixin:" in serializers_src
    assert '"custom_fields", "custom_field_data"' in serializers_src

    guarded_fields = {
        "SambaServerState": {
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
        },
        "SambaConfigFile": {"path", "content"},
        "SambaConfigSnapshot": {"snapshot_id", "content"},
        "SambaObservedShare": {"name", "path", "raw_params"},
        "SambaObservedUser": {"username", "sid"},
        "SambaObservedGroup": {"name", "sid", "members"},
        "SambaSession": {"username", "machine", "remote_ip", "share"},
        "SambaSyncRun": {"rpc_execution_ids", "error_message"},
    }
    for model_name, required_fields in guarded_fields.items():
        serializer_class = _class_node("api/serializers.py", f"{model_name}Serializer")
        assert any(
            isinstance(base, ast.Name) and base.id == "SecretSafeObservedSerializerMixin"
            for base in serializer_class.bases
        ), model_name
        field_assignment = next(
            node
            for node in serializer_class.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "secret_safe_fields"
                for target in node.targets
            )
        )
        assert required_fields <= set(ast.literal_eval(field_assignment.value)), model_name

        model_class = _class_node("models.py", model_name)
        clean_method = next(
            node
            for node in model_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "clean"
        )
        guard_call = next(
            node
            for node in ast.walk(clean_method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_validate_secret_free_fields"
        )
        model_guarded_fields = {
            ast.literal_eval(argument)
            for argument in guard_call.args[1:]
            if isinstance(argument, ast.Constant)
        }
        assert required_fields <= model_guarded_fields, model_name


def test_secret_name_detection_covers_flattened_and_qualified_credentials():
    src = read("models.py")
    secret_names = _literal_assignment("models.py", "_SECRET_FIELD_NAMES")
    short_secret_names = _literal_assignment("models.py", "_SHORT_SECRET_FIELD_NAMES")
    qualifiers = _literal_assignment("models.py", "_SECRET_VALUE_QUALIFIERS")

    assert 're.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()' in src
    assert {
        "authorization",
        "bind pw",
        "client key",
        "cookie",
        "cookies",
        "krb5 key",
        "keytab",
        "pkcs12",
        "session id",
        "trust auth incoming",
        "trust auth outgoing",
    } <= secret_names
    assert {"pass", "pw"} <= short_secret_names
    assert {"binary", "ciphertext", "data", "history", "material", "value"} <= qualifiers
    assert 'key_types & {"ec", "okp", "rsa"}' in src
    assert "for key, nested in normalized_items" in src
    assert "validate_no_secret_material(key, field_name=field_name)" in src
    assert "stripped.startswith" not in src
    assert 'r"^\\s*(?:basic|bearer)\\s+(?P<value>\\S+)\\s*$"' in src
    assert 'for separator in ("=", ":"):' in src


def test_sync_run_rejects_a_finish_before_its_start():
    sync_run_class = _class_node("models.py", "SambaSyncRun")
    clean_method = next(
        node
        for node in sync_run_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "clean"
    )
    clean_src = ast.get_source_segment(read("models.py"), clean_method)
    assert clean_src is not None
    assert "self.finished < self.started" in clean_src
    assert "finish time cannot be earlier" in clean_src


def test_observed_json_fields_enforce_their_documented_container_shapes():
    src = read("models.py")
    assert src.count("_validate_json_container(") == 5  # helper + four call sites
    for field_name in ("content", "raw_params", "members", "rpc_execution_ids"):
        assert f'self.{field_name},\n            field_name="{field_name}"' in src
    assert "def _validate_positive_integer_list(" in src
    assert "type(item) is not int or item <= 0" in src
    assert "_validate_positive_integer_list(\n            self.rpc_execution_ids," in src


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
    for _cls, _name, slug in MODELS:
        assert f'router.register("{slug}"' in src, slug


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


def test_samba_observed_migration_is_leaf_scoped_and_model_synced():
    path = PKG / "migrations" / "0003_samba_observed_state.py"
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    migration_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Migration"
    )
    dependencies = next(
        node
        for node in migration_class.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "dependencies"
            for target in node.targets
        )
    )
    assert ast.literal_eval(dependencies.value) == [
        ("netbox_fileserver", "0002_fileserverenrollmenttoken")
    ]

    migration_models = _migration_model_field_types(path)
    assert set(migration_models) == set(SAMBA_OBSERVED_MODEL_FIELDS)
    inherited_fields = {
        "id": "BigAutoField",
        "created": "DateTimeField",
        "last_updated": "DateTimeField",
        "custom_field_data": "JSONField",
        "tags": "TaggableManager",
    }
    for model_name in SAMBA_OBSERVED_MODEL_FIELDS:
        expected = inherited_fields | _model_field_types(model_name)
        assert migration_models[model_name] == expected, model_name

    assert src.count("on_delete=django.db.models.deletion.CASCADE") == 8
    assert src.count('to="netbox_fileserver.sambadomain"') == 8
    assert src.count("models.OneToOneField(") == 1
    assert src.count("models.ForeignKey(") == 7
    assert src.count("migrations.CreateModel(") == 8


def test_observed_sha256_fields_are_validated_in_models_and_migration():
    models_src = read("models.py")
    migration_src = read("migrations/0003_samba_observed_state.py")

    assert 'regex=r"^[0-9a-fA-F]{64}$"' in models_src
    assert models_src.count("validators=[_SHA256_VALIDATOR]") == 2
    assert migration_src.count("django.core.validators.RegexValidator(") == 2
    assert migration_src.count('regex="^[0-9a-fA-F]{64}$"') == 2


def test_observed_choice_fields_are_inlined_in_the_migration():
    migration_src = read("migrations/0003_samba_observed_state.py")
    for value, label in (
        ("in_sync", "In sync"),
        ("drifted", "Drifted"),
        ("missing_on_host", "Missing on host"),
        ("unmanaged", "Unmanaged"),
        ("running", "Running"),
        ("succeeded", "Succeeded"),
        ("partial", "Partial"),
        ("failed", "Failed"),
    ):
        assert f'("{value}", "{label}")' in migration_src


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
    searchable_models = {
        "FileServerDeployment",
        "SambaDomain",
        "NextcloudInstance",
        "FileShare",
        "DomainGroup",
        "SambaServerState",
        "SambaObservedShare",
        "SambaObservedUser",
        "SambaObservedGroup",
        "SambaSession",
        "SambaSyncRun",
    }
    assert src.count("@register_search") == len(searchable_models)
    for model_name in searchable_models:
        assert f"class {model_name}Index(SearchIndex):" in src
    for excluded_model in (
        "FileServerEnrollmentToken",
        "SambaConfigFile",
        "SambaConfigSnapshot",
    ):
        assert f"class {excluded_model}Index(" not in src
    assert "token_hash" not in src


# ──────────────────────────────── Security ────────────────────────────


def test_no_forbidden_patterns_in_python_sources():
    for rel in MODEL_FILES:
        src = read(rel)
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in src, f"{pattern} found in {rel}"


# ─────────────────── Full CRUD surface + reconciler contract ───────────────────

SAMBA_OBSERVED_MODEL_FIELDS = {
    "SambaServerState": (
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
    ),
    "SambaConfigFile": (
        "domain",
        "path",
        "content",
        "sha256",
        "size",
        "mtime",
        "is_primary",
        "fetched_at",
    ),
    "SambaConfigSnapshot": ("domain", "snapshot_id", "content"),
    "SambaObservedShare": (
        "domain",
        "name",
        "path",
        "raw_params",
        "browseable",
        "read_only",
        "guest_ok",
        "drift_state",
    ),
    "SambaObservedUser": ("domain", "username", "sid", "enabled", "last_logon"),
    "SambaObservedGroup": ("domain", "name", "sid", "members"),
    "SambaSession": (
        "domain",
        "username",
        "machine",
        "remote_ip",
        "share",
        "pid",
        "opened_at",
    ),
    "SambaSyncRun": (
        "domain",
        "started",
        "finished",
        "status",
        "rpc_execution_ids",
        "error_message",
    ),
}

# (ClassName, url/template model name, url slug)
MODELS = (
    ("FileServerDeployment", "fileserverdeployment", "deployments"),
    ("FileServerEnrollmentToken", "fileserverenrollmenttoken", "enrollment-tokens"),
    ("SambaDomain", "sambadomain", "samba-domains"),
    ("NextcloudInstance", "nextcloudinstance", "nextcloud-instances"),
    ("FileShare", "fileshare", "shares"),
    ("DomainGroup", "domaingroup", "domain-groups"),
    ("SambaServerState", "sambaserverstate", "samba-server-states"),
    ("SambaConfigFile", "sambaconfigfile", "samba-config-files"),
    ("SambaConfigSnapshot", "sambaconfigsnapshot", "samba-config-snapshots"),
    ("SambaObservedShare", "sambaobservedshare", "samba-observed-shares"),
    ("SambaObservedUser", "sambaobserveduser", "samba-observed-users"),
    ("SambaObservedGroup", "sambaobservedgroup", "samba-observed-groups"),
    ("SambaSession", "sambasession", "samba-sessions"),
    ("SambaSyncRun", "sambasyncrun", "samba-sync-runs"),
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
    assert src.count('read_only_fields = ("created", "last_updated")') == 13
    assert 'read_only_fields = ("status", "created", "last_updated")' in src
    assert "class FileServerDeploymentReconcilerSerializer" in src
    assert "allow_reconciler_status_write" in src
    # Belt-and-suspenders: no observed field name appears on a read_only line.
    for line in src.splitlines():
        if "read_only_fields" in line:
            for field in OBSERVED_FIELDS:
                assert field not in line, f"{field} must stay writable"


def test_every_api_viewset_wires_its_filterset():
    for cls, _name, _slug in MODELS:
        viewset = _class_node("api/views.py", f"{cls}ViewSet")
        assignment = next(
            node
            for node in viewset.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "filterset_class"
                for target in node.targets
            )
        )
        assert isinstance(assignment.value, ast.Name)
        assert assignment.value.id == f"{cls}FilterSet"


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

    for model_name, observed_fields in SAMBA_OBSERVED_MODEL_FIELDS.items():
        assert _form_meta_fields(f"{model_name}Form") == ("tags",), model_name
        bulk_form = _class_node("forms.py", f"{model_name}BulkEditForm")
        bulk_assignments = {
            target.id
            for node in bulk_form.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        assert bulk_assignments == {"model", "nullable_fields"}, model_name
        assert not (set(observed_fields) & bulk_assignments), model_name


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


def test_graphql_types_enforce_netbox_object_permissions():
    src = read("graphql/types.py")
    assert "from netbox.graphql.types import NetBoxObjectType" in src
    for cls, _name, _slug in MODELS:
        type_class = _class_node("graphql/types.py", f"{cls}Type")
        assert any(
            isinstance(base, ast.Name) and base.id == "NetBoxObjectType"
            for base in type_class.bases
        ), cls


def test_bulk_edit_is_wired_for_all_models():
    forms_src = read("forms.py")
    views_src = read("views.py")
    urls_src = read("urls.py")
    assert forms_src.count("(NetBoxModelBulkEditForm):") == len(MODELS)
    assert views_src.count("(generic.BulkEditView):") == len(MODELS)
    assert 'name=f"{name}_bulk_edit"' in urls_src


def test_every_model_has_the_full_plugin_surface():
    serializers = read("api/serializers.py")
    api_views = read("api/views.py")
    filtersets = read("filtersets.py")
    forms_src = read("forms.py")
    tables = read("tables.py")
    views_src = read("views.py")
    router = read("api/urls.py")
    graphql_types = read("graphql/types.py")
    graphql_schema = read("graphql/schema.py")
    query_names = {
        "FileServerDeployment": "fileserver_deployment",
        "FileServerEnrollmentToken": "fileserver_enrollment_token",
        "SambaDomain": "samba_domain",
        "NextcloudInstance": "nextcloud_instance",
        "FileShare": "file_share",
        "DomainGroup": "domain_group",
        "SambaServerState": "samba_server_state",
        "SambaConfigFile": "samba_config_file",
        "SambaConfigSnapshot": "samba_config_snapshot",
        "SambaObservedShare": "samba_observed_share",
        "SambaObservedUser": "samba_observed_user",
        "SambaObservedGroup": "samba_observed_group",
        "SambaSession": "samba_session",
        "SambaSyncRun": "samba_sync_run",
    }
    for cls, _name, slug in MODELS:
        assert f"class {cls}Serializer(" in serializers, cls
        assert f"class {cls}ViewSet(" in api_views, cls
        assert f'router.register("{slug}", views.{cls}ViewSet)' in router, cls
        assert f"class {cls}FilterSet(" in filtersets, cls
        assert f"class {cls}Form(" in forms_src, cls
        assert f"class {cls}BulkEditForm(" in forms_src, cls
        assert f"class {cls}Table(" in tables, cls
        assert f"class {cls}Type(NetBoxObjectType):" in graphql_types, cls
        query_name = query_names[cls]
        assert f"{query_name}: {cls}Type" in graphql_schema, cls
        assert f"{query_name}_list: list[{cls}Type]" in graphql_schema, cls
        for suffix in (
            "ListView",
            "View",
            "EditView",
            "DeleteView",
            "BulkEditView",
            "BulkDeleteView",
        ):
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

    assert urls.count("        include_add=False,") == len(SAMBA_OBSERVED_MODEL_FIELDS)


def test_observed_list_actions_only_advertise_routable_operations():
    assignment = next(
        node
        for node in ast.parse(read("views.py")).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "OBSERVED_STATE_LIST_ACTIONS"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Tuple)
    assert {
        element.id
        for element in assignment.value.elts
        if isinstance(element, ast.Name)
    } == {"BulkExport", "BulkEdit", "BulkDelete"}
