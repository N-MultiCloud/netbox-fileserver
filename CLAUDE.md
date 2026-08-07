# netbox-fileserver — Claude Code Guide

## Workspace Context

This file lives at `netbox-fileserver/CLAUDE.md` and is the primary AI-facing
guide for the `netbox-fileserver` plugin.
Workspace guidance: `/root/personal-context/CLAUDE.md`.
Per-repo deep-dive: `/root/personal-context/claude-reference/netbox-fileserver.md`.
Dependency map: `/root/personal-context/claude-reference/dependency-map.md`.

---

NetBox plugin that models the N-MultiCloud **File Server product** (managed
Samba AD/DC + Nextcloud) as **NetBox desired state**. NetBox is the source of
truth; an external **NMS file-server backend** reconciles Proxmox/Samba/Nextcloud
to match and writes observed status back. Depends on
[netbox-nms](https://git.nmulti.cloud/N-MultiCloud/netbox-nms) for the
`NMSBackend` connection registry and
[netbox-rpc](https://git.nmulti.cloud/N-MultiCloud/netbox-rpc) for the audited
Samba intent, execution ledger, and RQ procedure jobs.

Migration dependencies on NetBox core apps must target nodes present in both
NetBox 4.5.8 and 4.6.x while the plugin advertises 4.5 compatibility.

## Plugin Layout

```
netbox_fileserver/
├── __init__.py           NetBoxFileServerConfig + required plugins/job registration
├── choices.py            DeploymentStatusChoices, ACLRoleChoices, SambaFunctionalLevelChoices
├── models.py             6 desired/product models + 8 Samba observed-state models
├── filtersets.py         NetBoxModelFilterSet subclasses
├── forms.py              NetBoxModelForm + filter forms
├── tables.py             NetBoxTable subclasses
├── views.py              generic CRUD + bulk edit/delete per model
├── urls.py               URL patterns (per-model helper)
├── navigation.py         PluginMenu (Deployments / Samba / Nextcloud / Shares)
├── search.py             SearchIndex registrations (11; config bodies excluded)
├── template_content.py   Tenant + VirtualMachine detail-page panels
├── samba_sync.py         RPC dispatch/await/fold/redaction/persistence/drift engine
├── jobs.py               SambaSyncJob NetBox RQ runner
├── api/                  DRF serializers, viewsets, NetBoxRouter
├── graphql/              strawberry_django types + schema
├── migrations/0001_initial.py
├── migrations/0002_fileserverenrollmenttoken.py
├── migrations/0003_samba_observed_state.py
├── docs/enrollment.md    Enrollment token + pending-approval API contract
├── docs/samba-observed-state.md  Observed-state model/API/UI/security contract
└── templates/netbox_fileserver/…   flat detail templates + inc/ panels
```

## The integration object

`FileShare` is where the two worlds meet: **one row = one SMB share + its
Nextcloud external-storage mount**. Reconciling one `FileShare` configures Samba
(`path` + `acl_spec` + the VFS feature toggles) and Nextcloud (`nc_mount_*`)
consistently, and mirrors the `files_external:notify` daemon health into
`notify_active` for drift visibility.

`acl_spec` is a JSON list of `{"group": "<DomainGroup>", "role": "ro|rw|full|deny"}`.
`FileShare.clean()` validates the structure, the role against `ACLRoleChoices`,
and (once the domain's groups are modeled) that each `group` is a real
`DomainGroup` under the deployment's `SambaDomain`.

Per-share Samba VFS product features (rendered into the share's `vfs objects`
stack by the reconciler): `snapshots_enabled` (`vfs_shadow_copy2` = Previous
Versions / VSS — the feature the product plan's 5-point matrix validates) and
`recycle_enabled` (`vfs_recycle`). The Samba/Nextcloud upstream forks that
define this integration surface are vendored at
`nmulticloud-context/fileserver/{samba,nextcloud}/` — see their per-directory
`CLAUDE.md` (`samba/source3/modules/` for VFS, `samba/source4/` for the AD DC,
`nextcloud/server/apps/` for `files_external`/`user_ldap`).

## Critical Rules

1. **No secrets at rest in NetBox.** `FileServerDeployment.secret_ref` is a
   pointer (e.g. a Vault path) — never ciphertext. `FileServerEnrollmentToken`
   stores only a SHA-256 `token_hash`; plaintext is returned only once when
   minted and is never persisted. Do **not** add encrypted secret fields or
   import `netbox_nms.encryption` here.
2. **Observed fields are reconciler-written**:
   `NextcloudInstance.version`, `FileShare.nc_mount_id` / `notify_active`,
   `SambaDomain.ldaps_cert_expiry`, `NextcloudInstance.ldap_config_id`, and every
   field on `SambaServerState`, `SambaConfigFile`, `SambaConfigSnapshot`,
   `SambaObservedShare`, `SambaObservedUser`, `SambaObservedGroup`,
   `SambaSession`, and `SambaSyncRun`. They are API-writable (not read-only) and
   omitted from operator forms. `FileServerDeployment.status` is writable only
   through the `approve` action or the `File Server Reconcilers` service-account
   API path.
3. **Desired end users are NOT modeled** — `DomainGroup` is the desired ACL
   identity. `SambaObservedUser` is a non-secret read-side mirror, not a NetBox
   user. Passwords, hashes, keys, ciphertext, and credentials never belong in
   its schema or payloads.
4. **No** `eval`, `exec`, `os.system`, `pickle.loads`, `innerHTML`,
   `dangerouslySetInnerHTML` (security-guidance policy; enforced by
   `tests/test_static_contract.py`).
5. The hand-written migrations must stay in sync with `models.py` (choices +
   validators are inlined to keep `makemigrations` clean). Samba observed-state
   models live in `0003_samba_observed_state.py`, depending only on plugin leaf
   `0002_fileserverenrollmenttoken`.
6. Every plugin GraphQL model type must inherit
   `netbox.graphql.types.NetBoxObjectType`. Its `get_queryset()` implementation
   calls `queryset.restrict(user, "view")`; a plain Strawberry type silently
   bypasses NetBox object-level permissions.

## NMS stack integration

- `FileServerDeployment.backend` → `netbox_nms.NMSBackend` is the reconciler the
  webhook/loop drives. **Not yet implemented**: `nms-backend` does not
  currently proxy this plugin. There is no `netbox_fileserver` entry in
  `nms-backend`'s `automation/netbox/plugin_discovery.py::KNOWN_PLUGINS` and no
  dedicated `fileserver_plugin_proxy_router` (mirroring `pdm_plugin_proxy.py` /
  `ceph_plugin_proxy.py`). Adding both is a remaining Phase 1 task, not a
  shipped integration — see the Roadmap section below.
- Enrollment: `POST /api/plugins/fileserver/enrollment-tokens/consume/` accepts
  `token`, `vmid`, `hostname`, `ips`, `realm`, and `netbios`, validates the
  one-time tenant token, stamps `used_at`, and returns tenant plus optional
  deployment context. This endpoint requires a global reconciler service
  identity, not a tenant-scoped grant. The reconciler performs all object writes
  after that validation.
- Pending approval: `POST /api/plugins/fileserver/deployments/{id}/approve/`
  transitions `pending_approval` deployments to `planned` or `active`. It is
  gated to staff/superusers or the tenant's
  `Cloud Portal: <tenant-slug> :: Admins` group.
- Samba sync: `POST /api/plugins/fileserver/samba-domains/{id}/sync/` creates a
  `SambaSyncRun` and queues `SambaSyncJob`. It requires domain change access,
  an approved operator/reconciler identity, and the netbox-rpc intent/procedure
  execute permissions. The job dispatches only the seeded
  `FILESERVER_SAMBA_COLLECT_STATE` intent, records every child execution ID,
  polls for at most 300 seconds, and folds only successful procedure results.
  Collection replacement is fail-closed: server state requires the full
  version/service/config quartet and shares require both effective config and
  the authoritative share list. Config is redacted and revalidated before
  file/snapshot persistence. Drift is report-only and never auto-remediates.
  The shared-default-queue topology requires at least two RQ workers to avoid
  a single-sync deadlock; W concurrent domain syncs need W+1 workers to run in
  parallel rather than degrade to serialized, timeout-bounded execution (see
  `docs/samba-observed-state.md`).
- Live Samba sync is pending production registration of the
  `service.samba_1.*` backend handlers. Until that backend promotion lands,
  child executions fail closed as handler-not-registered; fixture-backed fold
  and drift behavior is still fully testable here.
- Deploy: `deploy-netbox-plugin fileserver` (whitelisted in
  `nmulticloud-context/deploy/bin/{deploy-netbox-plugin,nmc-deploy-lib}`), CI in
  `.gitea/workflows/deploy-production.yml` on push to `main`.

## Dev Commands

```bash
ruff check netbox_fileserver/ tests/
python -m compileall netbox_fileserver/
pytest tests/ -v        # import-free static-contract tests (no DB needed)
```

## Roadmap (File Server product)

This plugin is **Phase 1** (desired-state model + API). Remaining phases live as
Gitea sub-issues: golden LXC templates (`tpl-samba-dc`, `tpl-nextcloud`), the
FastAPI reconciler (NetBox → Proxmox/Samba/Nextcloud, webhook + drift loop), the
Next.js customer portal, network/edge (Traefik + per-tenant VLAN + WireGuard),
and the ops baseline (PBS backups, synthetic probes, nightly drift report).
Also outstanding: registering this plugin in `nms-backend` (`KNOWN_PLUGINS` entry
+ dedicated `fileserver_plugin_proxy_router`) so `/netbox/netbox-fileserver/plugin/*`
actually exists — see "NMS stack integration" above.
