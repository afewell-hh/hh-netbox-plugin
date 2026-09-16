"""Deployment prerequisites for the paste-only interchange UI (#684)."""

from django.conf import settings
from django.core.checks import Error, register

from netbox_hedgehog import HedgehogPluginConfig


def configured_interchange_body_limit():
    """Return the plugin's configured encoded-body maximum without mutation."""
    values = dict(HedgehogPluginConfig.default_settings['interchange_import_limits'])
    values.update(
        settings.PLUGINS_CONFIG.get('netbox_hedgehog', {}).get(
            'interchange_import_limits', {},
        )
    )
    return values['max_encoded_body_bytes']


@register()
def interchange_upload_limit_prerequisite(app_configs, **kwargs):
    required = configured_interchange_body_limit()
    host = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    if host is not None and host >= required:
        return []
    return [Error(
        'NetBox DATA_UPLOAD_MAX_MEMORY_SIZE is below the interchange paste limit.',
        hint=(
            'Set DATA_UPLOAD_MAX_MEMORY_SIZE to at least '
            f'{required} bytes in the NetBox deployment configuration, then restart NetBox. '
            f'Current host value: {host!r}; configured interchange value: {required}.'
        ),
        id='netbox_hedgehog.E001',
    )]
