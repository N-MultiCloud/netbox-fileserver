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
    min_version = "4.5.8"
    max_version = "4.6.99"
    # netbox-nms supplies the NMSBackend connection registry; netbox-rpc owns
    # the audited Samba procedure catalog, intents, execution ledger, and RQ
    # dispatch path used by this plugin's observed-state sync engine.
    required_plugins = ["netbox_nms", "netbox_rpc"]
    required_settings: list[str] = []
    default_settings: dict = {}

    def ready(self) -> None:
        super().ready()
        from . import jobs  # noqa: F401 -- register SambaSyncJob with NetBox


config = NetBoxFileServerConfig
