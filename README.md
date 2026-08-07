# netbox-fileserver

NetBox plugin that models the N-MultiCloud **File Server product** — a managed
**Samba AD/DC (SMB)** + **Nextcloud (Web Drive)** environment per customer — as
**NetBox desired state**, plus the Samba state observed by the reconciler.
NetBox's PostgreSQL database is the source of truth for the infrastructure
objects; an external **NMS file-server backend** reconciles
Proxmox/Samba/Nextcloud to match and refreshes the observed-state inventory.
Samba collection is dispatched exclusively through the audited `netbox-rpc`
intent/execution ledger; this plugin never connects to a managed host directly.

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
| `DomainGroup` | AD groups referenced by share ACLs, so `acl_spec` validates against real groups. Desired end users are **not** modeled — passwords/user churn stay in AD. |
| `SambaServerState` | One-to-one observed Samba version, systemd unit states, config digest, `testparm` result, and observation time for a domain. |
| `SambaConfigFile` | Last fetched non-secret content and metadata for an actual Samba config file; unique by domain and path. |
| `SambaConfigSnapshot` | Point-in-time JSON archive of a domain's non-secret config file set for diff and rollback workflows. |
| `SambaObservedShare` | Effective share configuration reported by Samba, including raw parameters and desired-vs-observed `drift_state`. |
| `SambaObservedUser` | Non-secret directory observability (`username`, SID, enabled state, last logon); not a NetBox user or desired identity. |
| `SambaObservedGroup` | Observed Samba group name, SID, and JSON member list. |
| `SambaSession` | Live `smbstatus` session data: user, client, address, share, PID, and open time. |
| `SambaSyncRun` | Audit record for one collection run, including status, RPC execution IDs, timing, and sanitized error text. |

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
3. **AD is authoritative for identities/passwords** (runtime). NetBox does not
   manage desired end users. `SambaObservedUser` is a read-side operational
   mirror and can never hold passwords, hashes, keys, ciphertext, or credentials.
4. **Observed Samba rows are reconciler-owned.** Their fields are writable over
   the API for reconciliation but are absent from operator create/edit and
   bulk-edit forms (only NetBox tags remain editable in those forms).
5. **GraphQL honors NetBox object permissions.** Every plugin model type extends
   `NetBoxObjectType`, which restricts querysets to objects the caller may view.

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
- `samba-domains/{id}/sync/` — permission-gated POST action that creates a
  `SambaSyncRun` and queues the RPC collect/fold job.
- `nextcloud-instances/`
- `shares/`
- `domain-groups/`
- `samba-server-states/`
- `samba-config-files/`
- `samba-config-snapshots/`
- `samba-observed-shares/`
- `samba-observed-users/`
- `samba-observed-groups/`
- `samba-sessions/`
- `samba-sync-runs/`

The reconciler reads desired state from these endpoints and PATCHes observed
fields back. Deployment `status` is writable only for the `File Server
Reconcilers` service-account group; tenant/admin approval uses
`deployments/{id}/approve/`.

The Samba sync action requires object-level change access to the domain,
staff/tenant-admin or `File Server Reconcilers` membership, and the
`netbox_rpc.execute_rpcintent` plus `netbox_rpc.execute_rpcprocedure`
permissions. The job invokes the seeded `fileserver.samba.collect_state`
intent, waits up to five minutes, folds only successful results, and reports
failed or timed-out children as a `partial`/`failed` `SambaSyncRun` without
blanking their last-known state.

See [docs/enrollment.md](docs/enrollment.md) for the enrollment token and
pending-approval lifecycle contract. See
[docs/samba-observed-state.md](docs/samba-observed-state.md) for the observed
model, API, UI, GraphQL, search, and write-ownership contract.

## Requirements

- NetBox 4.5.8 – 4.6.99
- Python ≥ 3.12
- `netbox-nms` ≥ 0.1.8, < 0.2.0 (provides the `NMSBackend` connection registry; older releases cannot migrate on NetBox 4.5.x)
- `netbox-rpc` ≥ 0.1.7, < 0.2.0 (provides the seeded Samba intents, audited
  execution ledger, and RQ procedure jobs; `FILESERVER_SAMBA_COLLECT_STATE`
  and `execute_intent()` do not exist at the 0.1.6 tag — see
  N-MultiCloud/netbox-rpc#219)

Migrations depend only on NetBox core migration nodes present in both NetBox
4.5.8 and 4.6.x so the plugin can build its migration graph across the
advertised compatibility window.

## Install

```bash
pip install -e ./netbox-fileserver          # into the NetBox venv
# configuration.py → PLUGINS = ["netbox_nms", "netbox_rpc", "netbox_fileserver"]
python manage.py migrate netbox_fileserver
```

## License

MIT — see [LICENSE](./LICENSE).
