from netbox.plugins.navigation import PluginMenu, PluginMenuButton, PluginMenuItem


def _item(name, label, add=True):
    buttons = ()
    if add:
        buttons = (
            PluginMenuButton(
                link=f"plugins:netbox_fileserver:{name}_add",
                title=f"Add {label}",
                icon_class="mdi mdi-plus-thick",
            ),
        )
    return PluginMenuItem(
        link=f"plugins:netbox_fileserver:{name}_list",
        link_text=label,
        buttons=buttons,
    )


menu = PluginMenu(
    label="File Server",
    groups=(
        (
            "Deployments",
            (_item("fileserverdeployment", "Deployments"),),
        ),
        (
            "Samba",
            (
                _item("sambadomain", "Samba Domains"),
                _item("domaingroup", "Domain Groups"),
            ),
        ),
        (
            "Nextcloud",
            (_item("nextcloudinstance", "Nextcloud Instances"),),
        ),
        (
            "Shares",
            (_item("fileshare", "File Shares"),),
        ),
    ),
    icon_class="mdi mdi-folder-network",
)
