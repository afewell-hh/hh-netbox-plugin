from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu
from netbox.choices import ButtonColorChoices

# Complete plugin menu with all CRD links
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
        ('Infrastructure', (
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
        )),
        ('VPC API', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpc_list',
                link_text='VPCs',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:vpc_add',
                        title='Add VPC',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:external_list',
                link_text='External Systems',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:external_add',
                        title='Add External System',
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
        ('Attachments & Peering', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:externalattachment_list',
                link_text='External Attachments',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:externalattachment_add',
                        title='Add External Attachment',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:externalpeering_list',
                link_text='External Peerings',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:externalpeering_add',
                        title='Add External Peering',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpcattachment_list',
                link_text='VPC Attachments',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:vpcattachment_add',
                        title='Add VPC Attachment',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpcpeering_list',
                link_text='VPC Peerings',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:vpcpeering_add',
                        title='Add VPC Peering',
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
                link='plugins:netbox_hedgehog:switchgroup_list',
                link_text='Switch Groups',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:switchgroup_add',
                        title='Add Switch Group',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vlannamespace_list',
                link_text='VLAN Namespaces',
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_hedgehog:vlannamespace_add',
                        title='Add VLAN Namespace',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN
                    ),
                )
            ),
        )),
    )
)