#!/usr/bin/env python3
# HIVE MIND RESEARCHER: Signal execution test script for NetBox container

import logging
import sys

# Setup signal trace logging
signal_logger = logging.getLogger('hedgehog.signals.trace')
signal_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s [TRACE] %(message)s'))
signal_logger.addHandler(handler)

print('🔍 HIVE MIND RESEARCHER: Testing Django signal execution in NetBox container')

try:
    from netbox_hedgehog.models import HedgehogFabric, VPC
    from django.db import transaction
    
    # Get the test fabric from Agent #15
    fabric = HedgehogFabric.objects.get(id=35, name='FGD Sync Validation Fabric')
    print(f'✅ Found test fabric: {fabric.name}')
    
    # Create a test VPC to trigger signals
    test_vpc_name = 'signal-test-vpc'
    
    # Delete existing test VPC if it exists
    VPC.objects.filter(fabric=fabric, name=test_vpc_name).delete()
    print(f'🧹 Cleaned up any existing test VPC: {test_vpc_name}')
    
    print(f'🚀 Creating new VPC {test_vpc_name} to test signal execution...')
    
    with transaction.atomic():
        vpc = VPC(
            fabric=fabric,
            name=test_vpc_name,
            namespace='default',
            spec={
                'ipv4Namespace': 'test-namespace',
                'subnets': ['10.1.0.0/24']
            },
            labels={'test': 'signal-execution'},
            annotations={'test.hedgehog.com/purpose': 'signal-testing'}
        )
        vpc.save()
        print(f'✅ VPC created: {vpc.name} (ID: {vpc.id})')
    
    print('✅ Signal execution test completed. Check logs for signal traces.')
    
except HedgehogFabric.DoesNotExist:
    print('❌ Test fabric (ID: 35) not found. Agent #15 validation may have failed.')
    
    # List available fabrics
    fabrics = HedgehogFabric.objects.all()
    print(f'📋 Available fabrics ({fabrics.count()}):')
    for f in fabrics:
        print(f'  - ID: {f.id}, Name: {f.name}')
        
except Exception as e:
    print(f'❌ Signal execution test failed: {e}')
    import traceback
    traceback.print_exc()