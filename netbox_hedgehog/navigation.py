from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu
from netbox.choices import ButtonColorChoices

# Expanded plugin menu with working URLs
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
        ('Management', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:fabric_list',
                link_text='Fabrics',
                buttons=()
            ),
            PluginMenuItem(
                link='plugins:netbox_hedgehog:vpc_list',
                link_text='VPCs',
                buttons=()
            ),
        )),
    )
)