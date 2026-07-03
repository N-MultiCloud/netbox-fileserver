# Enrollment + Pending Approval

`FileServerEnrollmentToken` supports the File Server auto-provisioning flow.
NetBox remains desired state; the reconciler performs object writes after it
validates a tenant-scoped enrollment request.

## Data Model

- `token_hash`: SHA-256 hash of the enrollment token. Plaintext is never stored.
- `tenant`: required `tenancy.Tenant` scope.
- `target_deployment`: optional `FileServerDeployment` the token enrolls.
- `expires_at`: TTL cutoff.
- `used_at`: set once when consumed.

`FileServerEnrollmentToken.mint_token()` returns `(instance, plaintext)` once.
`consume_plaintext()` hashes the supplied token, compares it with
`hmac.compare_digest()`, rejects expired or used tokens, and stamps `used_at`
inside a row lock.

## REST API

Base path: `/api/plugins/fileserver/`

- `POST enrollment-tokens/`: mint a token. The response includes `token` only
  for that create response; persisted rows expose only `token_hash`.
- `POST enrollment-tokens/consume/`: accepts `token`, `vmid`, `hostname`, `ips`,
  `realm`, and `netbios`. Requires
  `netbox_fileserver.change_fileserverenrollmenttoken` on the NetBox API token.
  The response returns tenant and optional deployment context for the reconciler.
- `POST deployments/{id}/approve/`: staff/superuser or
  `Cloud Portal: <tenant-slug> :: Admins` users may approve
  `pending_approval` deployments into `planned` or `active`.

The agent enrollment serializer is validation-only. The reconciler owns creation
or updates of VMs, deployments, Samba domains, Nextcloud instances, and IP rows.
