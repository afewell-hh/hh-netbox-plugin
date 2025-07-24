from netbox.plugins import PluginMenuItem, PluginMenu

# Complete plugin menu restored with placeholder views (16 total pages)
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
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:gitrepository_list',
                link_text='Git Repositories',
                buttons=()
            ),
        )),
        ('VPC API', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpc_list',
                link_text='VPCs',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:external_list',
                link_text='External Systems',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:ipv4namespace_list',
                link_text='IPv4 Namespaces',
                buttons=()
            ),
        )),
        ('Attachments & Peering', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:externalattachment_list',
                link_text='External Attachments',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:externalpeering_list',
                link_text='External Peerings',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpcattachment_list',
                link_text='VPC Attachments',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpcpeering_list',
                link_text='VPC Peerings',
                buttons=()
            ),
        )),
        ('Wiring API', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:connection_list',
                link_text='Connections',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:switch_list',
                link_text='Switches',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:server_list',
                link_text='Servers',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:switchgroup_list',
                link_text='Switch Groups',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vlannamespace_list',
                link_text='VLAN Namespaces',
                buttons=()
            ),
        )),
    )
)