# netbox-fileserver — Agent Guide

## Overview

NetBox plugin modeling the N-MultiCloud File Server product (Samba AD/DC +
Nextcloud) as **desired state**. NetBox = source of truth; an external NMS
file-server backend reconciles and writes observed status back. Depends on
`netbox-nms` (`NMSBackend` registry).

**Models:** `FileServerDeployment`, `FileServerEnrollmentToken`,
`SambaDomain`, `NextcloudInstance`, `FileShare` (the SMB↔Nextcloud integration
object), `DomainGroup`.

## Critical Rules

1. **No secrets at rest.** `secret_ref` is a pointer (Vault path), never
   ciphertext. Enrollment tokens persist only `token_hash` (SHA-256), never
   plaintext. Do not add encrypted fields or import `netbox_nms.encryption`.
2. **Observed fields** (`version`, `nc_mount_id`, `notify_active`,
   `ldaps_cert_expiry`, `ldap_config_id`) are reconciler-written — API-writable,
   not in the forms. `FileServerDeployment.status` is writable only through the
   `approve` action or the `File Server Reconcilers` service-account API path.
3. **End users are not modeled** — only `DomainGroup`.
4. **No** `eval`/`exec`/`os.system`/`pickle.loads`/`innerHTML`/
   `dangerouslySetInnerHTML` (enforced by the static-contract test).
5. Keep `migrations/0001_initial.py` consistent with `models.py`.

## File Map

| File | What it does |
|---|---|
| `netbox_fileserver/__init__.py` | Plugin config (`base_url="fileserver"`, `required_plugins=["netbox_nms"]`) |
| `netbox_fileserver/models.py` | 6 Django models |
| `netbox_fileserver/api/` | DRF serializers, viewsets, NetBoxRouter |
| `netbox_fileserver/graphql/` | strawberry_django types + schema |
| `netbox_fileserver/template_content.py` | Tenant + VM detail-page panels |
| `netbox_fileserver/migrations/0001_initial.py` | Initial DB schema |
| `netbox_fileserver/migrations/0002_fileserverenrollmenttoken.py` | Enrollment token schema |
| `docs/enrollment.md` | Enrollment token + pending-approval API contract |
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
