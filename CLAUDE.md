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
`NMSBackend` connection registry.

## Plugin Layout

```
netbox_fileserver/
├── __init__.py           NetBoxFileServerConfig (base_url="fileserver", required_plugins=["netbox_nms"])
├── choices.py            DeploymentStatusChoices, ACLRoleChoices, SambaFunctionalLevelChoices
├── models.py             FileServerDeployment, SambaDomain, NextcloudInstance, FileShare, DomainGroup
├── filtersets.py         NetBoxModelFilterSet subclasses
├── forms.py              NetBoxModelForm + filter forms
├── tables.py             NetBoxTable subclasses
├── views.py              generic CRUD + bulk edit/delete per model
├── urls.py               URL patterns (per-model helper)
├── navigation.py         PluginMenu (Deployments / Samba / Nextcloud / Shares)
├── search.py             SearchIndex registrations (5)
├── template_content.py   Tenant + VirtualMachine detail-page panels
├── api/                  DRF serializers, viewsets, NetBoxRouter
├── graphql/              strawberry_django types + schema
├── migrations/0001_initial.py
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
   pointer (e.g. a Vault path) — never ciphertext. Do **not** add encrypted
   secret fields or import `netbox_nms.encryption` here.
2. **Observed fields are reconciler-written**: `status`, `NextcloudInstance.version`,
   `FileShare.nc_mount_id` / `notify_active`, `SambaDomain.ldaps_cert_expiry`,
   `NextcloudInstance.ldap_config_id`. They are API-writable (not read-only) and
   omitted from the create/edit forms.
3. **End users are NOT modeled** — only `DomainGroup` (ACLs reference groups).
   Passwords / per-user churn stay in AD.
4. **No** `eval`, `exec`, `os.system`, `pickle.loads`, `innerHTML`,
   `dangerouslySetInnerHTML` (security-guidance policy; enforced by
   `tests/test_static_contract.py`).
5. The hand-written `migrations/0001_initial.py` must stay in sync with
   `models.py` (choices + validators are inlined to keep `makemigrations` clean).

## NMS stack integration

- `FileServerDeployment.backend` → `netbox_nms.NMSBackend` is the reconciler the
  webhook/loop drives. `nms-backend` proxies plugin CRUD at
  `/netbox/netbox-fileserver/plugin/*` (registered in its `KNOWN_PLUGINS`).
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
