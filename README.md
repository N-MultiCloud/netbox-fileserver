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
   path). Ciphertext/secrets live in the reconciler's ops store or Vault.
3. **AD is authoritative for identities/passwords** (runtime). NetBox models the
   infrastructure (domains, instances, shares, groups), not end users.

## REST API

Endpoints are served at `/api/plugins/fileserver/`:

- `deployments/`
- `samba-domains/`
- `nextcloud-instances/`
- `shares/`
- `domain-groups/`

The reconciler reads desired state from these endpoints and PATCHes the observed
fields (`status`, `version`, `nc_mount_id`, `notify_active`, `ldaps_cert_expiry`)
back.

## Requirements

- NetBox 4.5.0 – 4.6.99
- Python ≥ 3.12
- `netbox-nms` ≥ 0.1.6 (provides the `NMSBackend` connection registry)

## Install

```bash
pip install -e ./netbox-fileserver          # into the NetBox venv
# configuration.py → PLUGINS = ["netbox_nms", "netbox_fileserver"]
python manage.py migrate netbox_fileserver
```

## License

MIT — see [LICENSE](./LICENSE).
