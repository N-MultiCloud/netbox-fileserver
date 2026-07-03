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

Stored token hashes are internal only. REST list/detail responses, GraphQL, UI
detail pages, and global search must not disclose `token_hash`; the only secret
material returned by the API is the one-time `token` value on the token creation
response.

## REST API

Base path: `/api/plugins/fileserver/`

- `POST enrollment-tokens/`: mint a token. The response includes `token` only
  for that create response; persisted rows do not expose the stored hash.
- `POST enrollment-tokens/consume/`: accepts `token`, `vmid`, `hostname`, `ips`,
  `realm`, and `netbios`. Requires
  `netbox_fileserver.change_fileserverenrollmenttoken` on a global reconciler
  service identity. Do not grant this permission to tenant-scoped users or
  groups; the token object is not known until after the submitted plaintext is
  validated, so the permission check is intentionally object-less. The response
  returns tenant and optional deployment context for the reconciler.
- `POST deployments/{id}/approve/`: staff/superuser or
  `Cloud Portal: <tenant-slug> :: Admins` users may approve
  `pending_approval` deployments into `planned` or `active`.

The agent enrollment serializer is validation-only. The reconciler owns creation
or updates of VMs, deployments, Samba domains, Nextcloud instances, and IP rows.

Deployment `status` is not writable through the standard deployment serializer or
operator forms. The model rejects status transitions unless they are one of:

- `pending_approval` -> `planned` or `active` through the `approve` action.
- A reconciler-observed status write through the existing deployment PATCH
  endpoint by a NetBox user in the `File Server Reconcilers` group. That service
  account still needs the normal object-level change permission for the
  deployment rows it writes.

## Known Gaps / Required Operator Steps

- The sibling `netbox-nms` seed command must grant tenant-admin groups
  `netbox_fileserver.change_fileserverdeployment` constrained to
  `{"tenant_id": <pk>}`. Without that seed entry, tenant admins can belong to
  `Cloud Portal: <tenant-slug> :: Admins` but still fail the change-scoped
  queryset used by `POST deployments/{id}/approve/`. This depends on the approve
  action fetching deployments with a `change`-scoped restriction.
- Create or maintain a single global reconciler service identity for enrollment
  token consumption. Its permission set may include
  `netbox_fileserver.change_fileserverenrollmenttoken`; tenant-scoped Cloud
  Portal grants must not include that permission.
- Add the reconciler NetBox API user to `File Server Reconcilers` if it writes
  observed deployment `status` through REST PATCH. Tenant/admin users outside
  that group can still use `approve`, but their standard PATCH requests cannot
  write `status`.
