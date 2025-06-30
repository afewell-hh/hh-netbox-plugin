from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu
from netbox.choices import ButtonColorChoices

# Main plugin menu
menu = PluginMenu(
    label='Hedgehog',
    groups=(
        ('Overview', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:overview',
                link_text='Dashboard',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:topology',
                link_text='Network Topology',
                buttons=()
            ),
        )),
        ('Fabric Management', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:fabric_list',
                link_text='Fabrics',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:fabric_add',
                        title='Add Fabric',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:catalog',
                link_text='CRD Catalog',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:sync_all',
                        title='Sync All',
                        icon_class='mdi mdi-sync',
                        color=ButtonColorChoices.BLUE
                    ),
                )
            ),
        )),
        ('VPC API', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpc_list',
                link_text='VPCs',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:vpc_create',
                        title='Create VPC',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:external_list',
                link_text='Externals',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:external_add',
                        title='Add External',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:ipv4namespace_list',
                link_text='IPv4 Namespaces',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:ipv4namespace_add',
                        title='Add IPv4 Namespace',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
        )),
        ('Wiring API', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:connection_list',
                link_text='Connections',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:connection_add',
                        title='Add Connection',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:switch_list',
                link_text='Switches',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:switch_add',
                        title='Add Switch',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:server_list',
                link_text='Servers',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:server_add',
                        title='Add Server',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vlan_namespace_list',
                link_text='VLAN Namespaces',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:vlan_namespace_add',
                        title='Add VLAN Namespace',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
        )),
    )
)