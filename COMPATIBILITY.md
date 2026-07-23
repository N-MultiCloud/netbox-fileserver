# Compatibility

| netbox-fileserver | NetBox | Python | netbox-nms |
|---|---|---|---|
| 0.0.1 | 4.5.8 – 4.6.99 | ≥ 3.12 | ≥ 0.1.8, < 0.2.0 |

`min_version` / `max_version` are declared in
`netbox_fileserver/__init__.py::NetBoxFileServerConfig`. The plugin depends on
`netbox-nms` for the `NMSBackend` connection registry (the reconciler backend a
`FileServerDeployment` points at) and lists it as a `required_plugins` entry.

## NetBox release rotation

The production instance tracks the latest NetBox releases. When a new NetBox
version ships, bump `max_version` in `__init__.py` if it extends past `4.6.99`,
and re-verify the migration applies cleanly on the new release.
