#!/usr/bin/env python3
# HIVE MIND RESEARCHER: Check if app ready() method is importing signals properly

print('🔍 HIVE MIND RESEARCHER: Checking app ready() signal import')

try:
    from django.apps import apps
    
    # Get our app
    app = apps.get_app_config('netbox_hedgehog')
    print(f'✅ App config: {app}')
    print(f'App name: {app.name}')
    print(f'App ready called: {hasattr(app, "_ready_called")}')
    
    # Check if signals module can be imported
    try:
        from netbox_hedgehog import signals
        print(f'✅ Signals module imported: {signals}')
        
        # Check functions
        funcs = [f for f in dir(signals) if callable(getattr(signals, f)) and not f.startswith('_')]
        print(f'Signal functions: {funcs}')
        
        # Check if receiver decorators are working
        from django.db.models.signals import post_save
        print(f'Post-save signal: {post_save}')
        
        # Try to force re-import signals and see what happens
        print('🔧 Attempting to force re-register signals...')
        import importlib
        importlib.reload(signals)
        print('✅ Signals module reloaded')
        
    except Exception as e:
        print(f'❌ Signal import error: {e}')
        import traceback
        traceback.print_exc()
        
    # Try to check signal registration differently
    print('🔧 Testing signal registration inspection...')
    try:
        from django.db.models.signals import post_save
        from netbox_hedgehog.models import VPC
        
        # Check if we can see our signal in the registry 
        print(f'Post-save has receivers: {bool(post_save.has_listeners())}')
        
        # Try to connect the signal manually
        print('🔧 Trying manual signal connection...')
        from netbox_hedgehog.signals import on_crd_saved
        post_save.connect(on_crd_saved, weak=False)
        print('✅ Manual signal connection completed')
        
        # Test it
        print('🧪 Testing manually connected signal...')
        vpc = VPC(fabric_id=35, name='manual-connect-test', namespace='default', spec={})
        vpc.save()
        print('✅ Save after manual connection completed')
        
    except Exception as e:
        print(f'❌ Signal connection test failed: {e}')
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f'❌ App ready check failed: {e}')
    import traceback
    traceback.print_exc()