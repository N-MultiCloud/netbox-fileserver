# Samba Observed State

This plugin defines the read-side contract for Samba observed state: the
models, API, and UI that a Samba sync engine will populate once it collects
runtime data through guarded `netbox-rpc` procedures and persists the
sanitized result here (tracked as `netbox-fileserver#16`; not yet
implemented — see this repo's `CLAUDE.md`). Once populated, these rows
describe what the Samba host is actually reporting; they are not desired
configuration and do not replace `SambaDomain`, `FileShare`, or `DomainGroup`.

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
