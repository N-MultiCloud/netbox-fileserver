# netbox-fileserver — Agent Guide

## Overview

NetBox plugin modeling the N-MultiCloud File Server product (Samba AD/DC +
Nextcloud) as **desired state**. NetBox = source of truth; an external NMS
file-server backend reconciles and writes observed status back. Depends on
`netbox-nms` (`NMSBackend` registry).

Migration dependencies on NetBox core apps must target nodes present in both
NetBox 4.5.8 and 4.6.x while the plugin advertises 4.5 compatibility.

**Desired/product models:** `FileServerDeployment`,
`FileServerEnrollmentToken`, `SambaDomain`, `NextcloudInstance`, `FileShare`
(the SMB↔Nextcloud integration object), `DomainGroup`.

**Samba observed-state models:** `SambaServerState`, `SambaConfigFile`,
`SambaConfigSnapshot`, `SambaObservedShare`, `SambaObservedUser`,
`SambaObservedGroup`, `SambaSession`, `SambaSyncRun`.

## Critical Rules

1. **No secrets at rest.** `secret_ref` is a pointer (Vault path), never
   ciphertext. Enrollment tokens persist only `token_hash` (SHA-256), never
   plaintext. Do not add encrypted fields or import `netbox_nms.encryption`.
2. **Observed fields** (`version`, `nc_mount_id`, `notify_active`,
   `ldaps_cert_expiry`, `ldap_config_id`, and every field on the eight Samba
   observed-state models) are reconciler-written — API-writable, not in operator
   forms. `FileServerDeployment.status` is writable only through the `approve`
   action or the `File Server Reconcilers` service-account API path.
3. **Desired end users are not modeled.** `DomainGroup` is the desired ACL
   identity. `SambaObservedUser` is a non-secret operational mirror, not a
   NetBox user; never add password/hash/key/ciphertext/credential fields.
4. **No** `eval`/`exec`/`os.system`/`pickle.loads`/`innerHTML`/
   `dangerouslySetInnerHTML` (enforced by the static-contract test).
5. Keep migrations consistent with `models.py`; observed-state changes belong
   after leaf `0002_fileserverenrollmenttoken` in
   `0003_samba_observed_state.py`.

## File Map

| File | What it does |
|---|---|
| `netbox_fileserver/__init__.py` | Plugin config (`base_url="fileserver"`, `required_plugins=["netbox_nms"]`) |
| `netbox_fileserver/models.py` | 14 Django models (6 desired/product + 8 Samba observed) |
| `netbox_fileserver/api/` | DRF serializers, viewsets, NetBoxRouter |
| `netbox_fileserver/graphql/` | strawberry_django types + schema |
| `netbox_fileserver/template_content.py` | Tenant + VM detail-page panels |
| `netbox_fileserver/migrations/0001_initial.py` | Initial DB schema |
| `netbox_fileserver/migrations/0002_fileserverenrollmenttoken.py` | Enrollment token schema |
| `netbox_fileserver/migrations/0003_samba_observed_state.py` | Eight Samba observed-state tables |
| `docs/enrollment.md` | Enrollment token + pending-approval API contract |
| `docs/samba-observed-state.md` | Samba observed-state ownership, API, UI, and security contract |
| `tests/test_static_contract.py` | Import-free contract tests (CI, no DB) |

## Enrollment Flow

- `FileServerEnrollmentToken.mint_token()` returns plaintext exactly once and
  stores only `token_hash`.
- `POST /api/plugins/fileserver/enrollment-tokens/consume/` accepts the agent
  enrollment payload (`token`, `vmid`, `hostname`, `ips`, `realm`, `netbios`),
  requires a global service identity with `change_fileserverenrollmenttoken`,
  and marks the token used.
- `POST /api/plugins/fileserver/deployments/{id}/approve/` lets staff/superusers
  or `Cloud Portal: <tenant-slug> :: Admins` approve `pending_approval`
  deployments into `planned` or `active`.

## Dev Commands

```bash
ruff check netbox_fileserver/ tests/
python -m compileall netbox_fileserver/
pytest tests/ -v
```
