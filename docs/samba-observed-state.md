# Samba Observed State

This plugin defines and populates the read-side contract for Samba observed
state. The sync engine collects runtime data through guarded `netbox-rpc`
procedures and persists the sanitized result here. These rows describe what
the Samba host is actually reporting; they are not desired configuration and
do not replace `SambaDomain`, `FileShare`, or `DomainGroup`.

## RPC sync lifecycle

`POST /api/plugins/fileserver/samba-domains/{id}/sync/` creates a running
`SambaSyncRun`, enqueues `SambaSyncJob` on NetBox's default RQ queue, and
returns HTTP 202 with the NetBox job and sync-run IDs. Only one running sync is
accepted per domain. The caller needs:

- object-level `change` access to the `SambaDomain`;
- staff/superuser status, membership in the tenant's
  `Cloud Portal: <slug> :: Admins` group, or membership in
  `File Server Reconcilers`; and
- `netbox_rpc.execute_rpcintent` and
  `netbox_rpc.execute_rpcprocedure`.

The job loads `netbox_rpc.constants.FILESERVER_SAMBA_COLLECT_STATE` and calls
`execute_intent()` with the domain's content type and primary key. That seeded
intent creates the nine audited read executions for version, service state,
configuration read/test, share list, live status, users, groups, and domain
information. `rpc_execution_ids` is saved immediately after dispatch,
including any children committed before a partial fan-out error.

The await stage polls those rows to a terminal status for at most 300 seconds.
The enclosing job timeout is 360 seconds. Because `SambaSyncJob` holds a
worker slot for its *entire* poll loop while the child RPC executions it is
waiting on run on that same default queue, the NetBox RQ deployment MUST run
at least `W + 1` worker processes, where `W` is the maximum number of Samba
domain syncs that may legitimately be in flight at once. This is a hard
operational capacity requirement, not a tuning knob: even one in-flight sync
self-deadlocks against its own children on a single-worker deployment (it
still resolves, but only by burning the full 300-second timeout).

Under-provisioning `W` concurrent syncs against fewer than `W + 1` workers
does **not** degrade gracefully to serialized execution. If every worker ends
up occupied running `SambaSyncJob` poll loops, none are left free to execute
the child RPC procedures those loops are waiting on; the syncs do not queue
behind one another, they all independently run out their full 300-second poll
budget and terminate as timed-out failures. That is a correctness/outage risk
for any deployment that lets operators trigger overlapping syncs beyond the
provisioned worker headroom, not merely slower throughput. Until
N-MultiCloud/netbox-fileserver#28 (a dedicated sync-await queue that removes
this coupling entirely) lands, deployments must size RQ worker count to
expected concurrent sync load and treat that sizing as a release
prerequisite, not an optimization.

As a tripwire against the single-worst-case topology -- a deployment with
`W + 1` never provisioned at all, which self-starves *every* sync, not just
overlapping ones -- the `sync` action rejects the request outright with
`HTTP 503` before creating a `SambaSyncRun` if fewer than
`jobs.MIN_SAMBA_SYNC_WORKERS` (2) workers are registered on the sync queue.
This only catches the zero-headroom case; it cannot detect that all
registered workers are already busy on unrelated jobs, so correct sizing for
expected concurrent sync load remains a deployment responsibility, not
something this check fully substitutes for.

### Fold and replacement ownership

`fold_result(procedure_name, result)` performs no I/O and returns unsaved model
instances. Persistence is transaction-scoped by collection:

| State | Required successful procedure(s) | Failure behavior |
|---|---|---|
| Server version/services/config digest/test result | `version`, `service_status`, `config_read`, `config_test` | Keep the prior row and its `observed_at`. |
| Primary config file + content-addressed snapshot | `config_read` | Keep prior config rows/snapshots. |
| Shares + drift | `config_test` and `list_shares` | Keep every prior share row; do not blank rich parameters from a name-only result. |
| Sessions | `status_report` | Keep prior sessions. |
| Users | `user_list` | Keep prior users. |
| Groups | `group_list` | Keep prior groups. |

The current `config_read` RPC result has content and SHA-256 but no filesystem
size or modification time. The fold computes byte size from the returned raw
body and uses the collection timestamp for both `mtime` and `fetched_at`; the
stored digest remains the host-reported value. Likewise, `user_list` and
`group_list` do not currently return SID/enabled/last-logon metadata, so those
existing model fields retain their non-secret blank/default representations.

Successful authoritative collection results delete rows that vanished from the
host. Desired shares absent from the authoritative list are retained/created as
`missing_on_host` placeholders; observed shares with no desired `FileShare`
are `unmanaged`. A partial run may still refresh an independently successful
collection, but never the collection owned by a failed or timed-out procedure.

The current observed schema has no columns for the `domain_info` response, so
that known procedure has an explicit no-write fold branch. It is still audited
and participates in whole-run success classification; the engine deliberately
does not overwrite desired `SambaDomain.realm`, `netbios_name`, or
`functional_level` fields with observed values.

### Drift comparison

The engine compares desired and observed share `name`, `path`, `smb_enabled`,
`acl_spec`, `snapshots_enabled`, and `recycle_enabled`. Effective `testparm -s`
parameters are stored in sanitized `raw_params`: presence means SMB enabled;
the standard valid/read/write/admin/invalid user lists map to ACL roles; and
`vfs objects` supplies the `shadow_copy2` and `recycle` flags. The result is
`in_sync`, `drifted`, `missing_on_host`, or `unmanaged`. Detection is read-only
and never dispatches the deploy-config intent.

## Data model

Every observed model subclasses `NetBoxModel`, cascades from `SambaDomain`, and
therefore supports NetBox tags, custom fields, journaling, and change logging.

| Model | Cardinality and contents |
|---|---|
| `SambaServerState` | One-to-one per domain: Samba version; active, sub, and unit-file state for `smbd`, `nmbd`, `winbind`, and `samba-ad-dc`; validated config SHA-256; `testparm_ok`; `observed_at`. |
| `SambaConfigFile` | Many per domain: path, sanitized content, validated SHA-256, byte size, mtime, primary marker, and fetch time. Domain + path is unique. |
| `SambaConfigSnapshot` | Many per domain: a unique snapshot identifier and JSON archive of a sanitized config file set. The inherited `created` timestamp records capture time. |
| `SambaObservedShare` | Many per domain: name, path, sanitized raw parameters, access flags, and desired-vs-observed drift state. Domain + name is unique. |
| `SambaObservedUser` | Many per domain: username, SID, enabled state, and last logon only. Domain + username is unique. |
| `SambaObservedGroup` | Many per domain: name, SID, and a JSON member list. Domain + name is unique. |
| `SambaSession` | Many per domain: username, machine, remote IP, share, PID, and open time from `smbstatus`. |
| `SambaSyncRun` | Many per domain: start/finish time, run status, RPC execution IDs, and sanitized error text. A finish time cannot predate the run's start. |

Deleting a `SambaDomain` deletes all of its observed rows. The observed tables
do not add relationships to NetBox users and do not make Samba users into
desired-state objects.

## REST API and GraphQL

The REST collections under `/api/plugins/fileserver/` are:

- `samba-server-states/`
- `samba-config-files/`
- `samba-config-snapshots/`
- `samba-observed-shares/`
- `samba-observed-users/`
- `samba-observed-groups/`
- `samba-sessions/`
- `samba-sync-runs/`

Each collection has the normal NetBox list, retrieve, create, update, partial
update, and delete surface. The GraphQL schema exposes singular and list queries
for each model. Reconciler service identities still need the corresponding
NetBox object permissions; membership in `File Server Reconcilers` does not by
itself bypass NetBox authorization. All plugin GraphQL types inherit
`NetBoxObjectType`, whose restricted queryset enforces the caller's object-level
view permissions.

## UI and search

Each model has list, detail, delete, changelog, journal, export, and bulk-delete pages.
Create/edit and bulk-edit forms intentionally expose only NetBox metadata such
as tags; domain relationships and runtime values are reconciler-owned and are
not operator-editable. Import and rename actions are omitted because observed
rows are created and named only by the reconciler. Navigation groups all eight
pages under **Samba Observed** and does not present add buttons.

Global search indexes server state, observed shares/users/groups, sessions, and
sync runs. `SambaConfigFile` and `SambaConfigSnapshot` are deliberately excluded
because config bodies are large and can contain operational host detail. Apply
appropriately narrow object permissions to their REST, GraphQL, and detail-page
surfaces as well.

## Secret handling

`SambaObservedUser` stores exactly `domain`, `username`, `sid`, `enabled`, and
`last_logon`. It has no password, NT/LM hash, credential, secret, key, or
ciphertext field. The observed serializers reject recognizable secret-bearing
keys (including camelCase, dotted, bracketed, slashed, short `pass`/`pw`
aliases, and value/history variants), assignments even when they occur on
commented lines, authorization headers, command-line credentials,
inline-credential URLs, password-hash formats/dumps, private JWKs, and PEM,
SSH2, PGP, or PuTTY private-key material. JSON keys are scanned as persisted
text as well as interpreted as field names. Model validation provides the same
guard for config content, raw share parameters, and sync error text. JSON
containers are also shape-checked: snapshots and raw share parameters are
objects, while group members and RPC execution IDs are lists. RPC execution IDs
must be positive integers, matching the `netbox-rpc` primary-key contract.

The collector must redact secrets before sending a payload. Raw passwords,
hashes, keys, tokens, and credentials must never be accepted as observed-state
request parameters or persisted in NetBox.

The fold stage adds a second fail-closed boundary. It redacts secret-bearing
assignment lines (including `encrypt passwords = yes`), validator-rejected
lines, and complete private-key blocks before constructing either
`SambaConfigFile.content` or `SambaConfigSnapshot.content`. It validates the
complete redacted body with `validate_no_secret_material()`; if any unsafe
material remains, the entire body is replaced with a redaction marker. The
stored SHA-256 remains the host-reported digest of the original config so it
can still identify the collected version without storing the unsafe bytes.

Live execution also requires the `service.samba_1.*` backend handlers to be
registered in the deployed RPC backend. Until that backend release is
promoted, dispatch remains auditable but child executions will fail closed
with a handler-not-registered error and the sync run will be `failed` or
`partial`.
