# netbox-fileserver — Agent Guide

## Overview

NetBox plugin modeling the N-MultiCloud File Server product (Samba AD/DC +
Nextcloud) as **desired state**. NetBox = source of truth; an external NMS
file-server backend reconciles and writes observed status back. Depends on
`netbox-nms` (`NMSBackend` registry) and `netbox-rpc` (audited Samba intents
and executions).

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
6. Every plugin GraphQL model type must inherit
   `netbox.graphql.types.NetBoxObjectType`; its `get_queryset()` hook applies
   NetBox object-level view restrictions. Plain Strawberry types bypass that
   permission boundary.

## File Map

| File | What it does |
|---|---|
| `netbox_fileserver/__init__.py` | Plugin config and required-plugin/job registration |
| `netbox_fileserver/models.py` | 14 Django models (6 desired/product + 8 Samba observed) |
| `netbox_fileserver/samba_sync.py` | RPC intent dispatch, bounded await, pure fold/redaction, persistence, and drift |
| `netbox_fileserver/jobs.py` | `SambaSyncJob` NetBox RQ runner |
| `netbox_fileserver/api/` | DRF serializers, viewsets, NetBoxRouter |
| `netbox_fileserver/graphql/` | strawberry_django types + schema |
| `netbox_fileserver/template_content.py` | Tenant + VM detail-page panels |
| `netbox_fileserver/migrations/0001_initial.py` | Initial DB schema |
| `netbox_fileserver/migrations/0002_fileserverenrollmenttoken.py` | Enrollment token schema |
| `netbox_fileserver/migrations/0003_samba_observed_state.py` | Eight Samba observed-state tables |
| `docs/enrollment.md` | Enrollment token + pending-approval API contract |
| `docs/samba-observed-state.md` | Samba observed-state ownership, API, UI, and security contract |
| `tests/test_static_contract.py` | Import-free contract tests (CI, no DB) |
| `tests/test_samba_sync.py` | Import-free fixture tests for folds, redaction, drift, and failure gates |

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

## Samba Sync Flow

- `POST /api/plugins/fileserver/samba-domains/{id}/sync/` requires domain
  change access, an approved operator/reconciler identity, and both netbox-rpc
  execute permissions; it returns HTTP 202 with RQ job and sync-run IDs.
- `SambaSyncJob` calls only `execute_intent(FILESERVER_SAMBA_COLLECT_STATE, …)`
  and records its child execution primary keys. Never replace this with direct
  procedure creation, backend HTTP, SSH, or local commands.
- Collection replacement is procedure-owned and fail-closed. In particular,
  shares require successful `config_test` plus `list_shares`; server
  `observed_at` requires the complete version/service/config-read/config-test
  quartet.
- Config fold must run `redact_secret_material()` before either config model is
  constructed. Do not weaken or catch-and-ignore `validate_no_secret_material()`.
- Drift is read-only and compares name/path/SMB enabled/ACL/snapshot/recycle
  state. It must never invoke the deploy-config intent.
- The default-queue polling topology needs at least two NetBox RQ workers. Live
  calls remain unverifiable until the Samba handler family is deployed by the
  RPC backend promotion.

## Dev Commands

```bash
ruff check netbox_fileserver/ tests/
python -m compileall netbox_fileserver/
pytest tests/ -v
```

## Public quality workflow

GitHub Actions runs the complete existing Ruff, compilation and import-free
pytest suite on isolated Ubuntu 24.04 with Python 3.12. Main and develop pushes,
pull requests and explicit manual quality requests use the same commands.
The workflow does not install the private plugin dependencies, provision NetBox
or a database, call production, publish packages or use deployment credentials.
Keep all original test modules and assertions when changing CI. The native
Gitea workflows remain separate; never move their production commands or trusted
runner into the public quality job. Only superseded pull-request quality may
be cancelled; main, develop and manual qualifications remain independent.
