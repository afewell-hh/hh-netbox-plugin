from netbox.plugins import PluginMenuItem, PluginMenu

# Complete plugin menu restored with placeholder views (16 total pages)
menu = PluginMenu(
    label='Hedgehog',
    groups=(
        ('Overview', (
            PluginMenuItem(
                link='plugins:hedgehog:overview',
                link_text='Dashboard',
                buttons=()
            ),
            # Network Topology - Hidden for now as feature is not implemented
            # PluginMenuItem(
            #     link='plugins:hedgehog:topology',
            #     link_text='Network Topology',
            #     buttons=()
            # ),
        )),
        ('Infrastructure', (
            PluginMenuItem(
                link='plugins:hedgehog:fabric_list',
                link_text='Fabrics',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:gitrepository_list',
                link_text='Git Repositories',
                buttons=()
            ),
        )),
        ('VPC API', (
            PluginMenuItem(
                link='plugins:hedgehog:vpc_list',
                link_text='VPCs',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:external_list',
                link_text='External Systems',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:ipv4namespace_list',
                link_text='IPv4 Namespaces',
                buttons=()
            ),
        )),
        ('Attachments & Peering', (
            PluginMenuItem(
                link='plugins:hedgehog:externalattachment_list',
                link_text='External Attachments',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:externalpeering_list',
                link_text='External Peerings',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:vpcattachment_list',
                link_text='VPC Attachments',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:vpcpeering_list',
                link_text='VPC Peerings',
                buttons=()
            ),
        )),
        ('Wiring API', (
            PluginMenuItem(
                link='plugins:hedgehog:connection_list',
                link_text='Connections',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:switch_list',
                link_text='Switches',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:server_list',
                link_text='Servers',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:switchgroup_list',
                link_text='Switch Groups',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:hedgehog:vlannamespace_list',
                link_text='VLAN Namespaces',
                buttons=()
            ),
        )),
    )
)