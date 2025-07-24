#!/usr/bin/env python3
"""
Check the database directly to see if state fields exist and have data.
Run this inside the NetBox Docker container.
"""

import subprocess
import sys

def run_django_shell_command(command):
    """Run a Django shell command inside the NetBox container"""
    try:
        # Construct the docker exec command
        docker_cmd = [
            'sudo', 'docker', 'exec', '-i', 'netbox-docker-netbox-1',
            'python', '/opt/netbox/netbox/manage.py', 'shell'
        ]
        
        # Run the command
        process = subprocess.Popen(
            docker_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=command)
        
        return {
            'returncode': process.returncode,
            'stdout': stdout,
            'stderr': stderr
        }
        
    except Exception as e:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e)
        }

def check_state_fields():
    """Check if state fields exist and have data"""
    print("=== CHECKING DATABASE STATE FIELDS ===")
    
    django_command = """
import sys
try:
    from netbox_hedgehog.models.vpc_api import Server, VPC
    from netbox_hedgehog.models.wiring_api import Switch, Connection
    
    # Check Server model
    print("Checking Server model:")
    servers = Server.objects.all()
    print(f"  Total servers: {servers.count()}")
    
    if servers.exists():
        first_server = servers.first()
        print(f"  First server: {first_server.name}")
        
        # Check if state field exists
        if hasattr(first_server, 'state'):
            print(f"  Has state field: YES")
            print(f"  State value: {first_server.state}")
            
            # Check state distribution
            from collections import Counter
            states = [s.state for s in servers if s.state]
            state_counts = Counter(states)
            print(f"  State distribution: {dict(state_counts)}")
        else:
            print(f"  Has state field: NO")
        
        # Check other fields for debugging
        print(f"  Sample server fields: {[field.name for field in first_server._meta.fields][:10]}")
    
    print("\\nChecking Switch model:")
    switches = Switch.objects.all()
    print(f"  Total switches: {switches.count()}")
    
    if switches.exists():
        first_switch = switches.first()
        print(f"  First switch: {first_switch.name}")
        
        if hasattr(first_switch, 'state'):
            print(f"  Has state field: YES")
            print(f"  State value: {first_switch.state}")
        else:
            print(f"  Has state field: NO")
    
    print("\\nChecking Connection model:")
    connections = Connection.objects.all()
    print(f"  Total connections: {connections.count()}")
    
    if connections.exists():
        first_connection = connections.first()
        print(f"  First connection: {first_connection.name}")
        
        if hasattr(first_connection, 'state'):
            print(f"  Has state field: YES")
            print(f"  State value: {first_connection.state}")
        else:
            print(f"  Has state field: NO")
    
    print("\\nChecking VPC model:")
    vpcs = VPC.objects.all()
    print(f"  Total VPCs: {vpcs.count()}")
    
    if vpcs.exists():
        first_vpc = vpcs.first()
        print(f"  First VPC: {first_vpc.name}")
        
        if hasattr(first_vpc, 'state'):
            print(f"  Has state field: YES")
            print(f"  State value: {first_vpc.state}")
        else:
            print(f"  Has state field: NO")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
"""
    
    result = run_django_shell_command(django_command)
    
    if result['returncode'] == 0:
        print(result['stdout'])
    else:
        print(f"Error running Django shell command:")
        print(f"STDERR: {result['stderr']}")
        print(f"STDOUT: {result['stdout']}")

def check_template_state_display():
    """Check if templates are displaying state fields"""
    print("\n=== CHECKING TEMPLATE STATE DISPLAY ===")
    
    # Check a few key templates
    templates_to_check = [
        '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/server_detail.html',
        '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/switch_detail_simple.html',
        '/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/connection_detail_simple.html'
    ]
    
    for template_path in templates_to_check:
        try:
            with open(template_path, 'r') as f:
                content = f.read()
                
            template_name = template_path.split('/')[-1]
            print(f"\nChecking {template_name}:")
            
            # Look for state-related content
            state_mentions = content.lower().count('state')
            status_mentions = content.lower().count('status')
            
            print(f"  'state' mentions: {state_mentions}")
            print(f"  'status' mentions: {status_mentions}")
            
            # Look for specific state display patterns
            if 'object.state' in content:
                print(f"  ✓ Contains 'object.state' reference")
            else:
                print(f"  ✗ No 'object.state' reference found")
                
            if 'object.status' in content:
                print(f"  ✓ Contains 'object.status' reference")
            else:
                print(f"  ✗ No 'object.status' reference found")
                
        except FileNotFoundError:
            print(f"\nTemplate not found: {template_name}")
        except Exception as e:
            print(f"\nError checking {template_name}: {e}")

if __name__ == '__main__':
    check_state_fields()
    check_template_state_display()