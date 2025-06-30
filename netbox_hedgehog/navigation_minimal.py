from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu
from netbox.choices import ButtonColorChoices

# Minimal plugin menu with only working URLs
menu = PluginMenu(
    label='Hedgehog',
    groups=(
        ('Overview', (
            PluginMenuItem(
                link='plugins:netbox_hedgehog:overview',
                link_text='Dashboard',
                buttons=()
            ),
        )),
    )
)