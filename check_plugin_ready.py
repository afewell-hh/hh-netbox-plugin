#!/usr/bin/env python3
# HIVE MIND RESEARCHER: Check plugin configuration

print('🔍 HIVE MIND RESEARCHER: Checking plugin configuration')

try:
    from netbox.plugins import PluginConfig
    from netbox_hedgehog import HedgehogPluginConfig
    
    print(f'PluginConfig: {PluginConfig}')
    print(f'PluginConfig methods: {[m for m in dir(PluginConfig) if not m.startswith("_")]}')
    
    # Check if PluginConfig has ready method
    if hasattr(PluginConfig, 'ready'):
        print('✅ PluginConfig has ready method')
    else:
        print('❌ PluginConfig has NO ready method')
    
    # Check our config
    print(f'HedgehogPluginConfig: {HedgehogPluginConfig}')
    print(f'HedgehogPluginConfig methods: {[m for m in dir(HedgehogPluginConfig) if not m.startswith("_")]}')
    
    if hasattr(HedgehogPluginConfig, 'ready'):
        print('✅ HedgehogPluginConfig has ready method')
    else:
        print('❌ HedgehogPluginConfig has NO ready method')
    
    # Check the apps configuration
    from django.apps import apps
    
    print('\n🔍 Available app configs:')
    for app_name, app_config in apps.app_configs.items():
        if 'hedgehog' in app_name.lower():
            print(f'  {app_name}: {app_config.__class__.__name__} - {type(app_config)}')
            if hasattr(app_config, 'ready'):
                print(f'    Has ready method: {app_config.ready}')
            else:
                print('    NO ready method')
                
except Exception as e:
    print(f'❌ Plugin config check failed: {e}')
    import traceback
    traceback.print_exc()