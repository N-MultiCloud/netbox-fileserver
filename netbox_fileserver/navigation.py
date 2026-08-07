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
            (
                _item("fileserverdeployment", "Deployments"),
                _item("fileserverenrollmenttoken", "Enrollment Tokens"),
            ),
        ),
        (
            "Samba",
            (
                _item("sambadomain", "Samba Domains"),
                _item("domaingroup", "Domain Groups"),
            ),
        ),
        (
            "Samba Observed",
            (
                _item("sambaserverstate", "Server States", add=False),
                _item("sambaconfigfile", "Config Files", add=False),
                _item("sambaconfigsnapshot", "Config Snapshots", add=False),
                _item("sambaobservedshare", "Observed Shares", add=False),
                _item("sambaobserveduser", "Observed Users", add=False),
                _item("sambaobservedgroup", "Observed Groups", add=False),
                _item("sambasession", "Sessions", add=False),
                _item("sambasyncrun", "Sync Runs", add=False),
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
