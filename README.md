# netbox-fileserver

NetBox plugin that models the N-MultiCloud **File Server product** — a managed
**Samba AD/DC (SMB)** + **Nextcloud (Web Drive)** environment per customer — as
**NetBox desired state**. NetBox's PostgreSQL database is the source of truth for
the infrastructure objects; an external **NMS file-server backend** reconciles
Proxmox/Samba/Nextcloud to match, and writes the observed status back.

This is the same pattern as `netbox-proxbox`, one layer up the stack:

> NetBox holds desired state · devices hold runtime state · the reconciler
> converges the two. Nobody edits a tenant by SSHing into a container.

## Models

| Model | Purpose |
|---|---|
| `FileServerDeployment` | One sold product instance = one customer environment. FK to `tenancy.Tenant`, `ipam.VLAN`/`Prefix`, and the reconciler `netbox_nms.NMSBackend`. Holds `fqdn`, plan sizing, and a `secret_ref` (**pointer only**, never the secret). |
| `FileServerEnrollmentToken` | One-time tenant-scoped enrollment token for auto-provisioning. Stores only `token_hash` (SHA-256), `tenant`, optional `target_deployment`, `expires_at`, and `used_at`; plaintext is returned only once when minted. |
| `SambaDomain` | The Samba AD/DC (`realm`, `netbios_name`, DC VM/IP, observed `ldaps_cert_expiry`). |
| `NextcloudInstance` | The Nextcloud instance (VM/IP, observed `version`, `ldap_config_id`). |
| `FileShare` | **The integration object** — one row describes both the SMB share (path, `acl_spec`, and the `snapshots_enabled`/`recycle_enabled` Samba VFS toggles) and its Nextcloud external-storage mount (`nc_mount_*`, observed `notify_active`). |
| `DomainGroup` | AD groups referenced by share ACLs, so `acl_spec` validates against real groups. End users are **not** modeled — passwords/user churn stay in AD. |

All models subclass `NetBoxModel`, so change-logging, custom fields, tags,
journaling, and **event rules/webhooks** work natively — the webhook is the
reconciliation trigger.

## Design rules

1. **NetBox = desired state.** Never write NetBox's PostgreSQL directly; all
   access is through the REST/GraphQL API.
2. **No secrets at rest in NetBox.** `secret_ref` is a pointer (e.g. a Vault
   path). Enrollment tokens store only a SHA-256 `token_hash`; plaintext tokens
   are returned once on mint and are never persisted, and the stored hash is not
   exposed through search, REST, GraphQL, or the UI. Ciphertext/secrets live in
   the reconciler's ops store or Vault.
3. **AD is authoritative for identities/passwords** (runtime). NetBox models the
   infrastructure (domains, instances, shares, groups), not end users.

## REST API

Endpoints are served at `/api/plugins/fileserver/`:

- `deployments/`
- `deployments/{id}/approve/` — POST approval action for staff or the tenant's
  Cloud Portal admin group; pending deployments transition to `planned` by
  default or `active` when requested.
- `enrollment-tokens/` — CRUD/mint endpoint for one-time enrollment tokens.
- `enrollment-tokens/consume/` — service-token permission-gated POST endpoint
  used by the reconciler to validate an agent enrollment payload and atomically
  mark a token as used.
- `samba-domains/`
- `nextcloud-instances/`
- `shares/`
- `domain-groups/`

The reconciler reads desired state from these endpoints and PATCHes observed
fields back. Deployment `status` is writable only for the `File Server
Reconcilers` service-account group; tenant/admin approval uses
`deployments/{id}/approve/`.

See [docs/enrollment.md](docs/enrollment.md) for the enrollment token and
pending-approval lifecycle contract.

## Requirements

- NetBox 4.5.0 – 4.6.99
- Python ≥ 3.12
- `netbox-nms` ≥ 0.1.6 (provides the `NMSBackend` connection registry)

Migrations depend only on NetBox core migration nodes present in both NetBox
4.5.8 and 4.6.x so the plugin can build its migration graph across the
advertised compatibility window.

## Install

```bash
pip install -e ./netbox-fileserver          # into the NetBox venv
# configuration.py → PLUGINS = ["netbox_nms", "netbox_fileserver"]
python manage.py migrate netbox_fileserver
```

## License

MIT — see [LICENSE](./LICENSE).
