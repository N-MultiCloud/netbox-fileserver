from netbox.plugins import PluginConfig


class NetBoxFileServerConfig(PluginConfig):
    name = "netbox_fileserver"
    verbose_name = "File Server (Samba + Nextcloud)"
    description = (
        "Models managed Samba AD/DC + Nextcloud file-server deployments as "
        "NetBox desired state, reconciled by the NMS file-server backend"
    )
    version = "0.0.1"
    base_url = "fileserver"
    author = "Emerson Felipe"
    author_email = "emerson.felipe@nmultifibra.com.br"
    min_version = "4.5.0"
    max_version = "4.6.99"
    # netbox-nms supplies the NMSBackend connection registry that a
    # FileServerDeployment points at (its reconciler backend). NetBox
    # auto-discovers search.py and template_content.template_extensions.
    required_plugins = ["netbox_nms"]
    required_settings: list[str] = []
    default_settings: dict = {}


config = NetBoxFileServerConfig
