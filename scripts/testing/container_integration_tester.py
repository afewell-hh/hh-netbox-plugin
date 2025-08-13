#!/usr/bin/env python3
"""
Container Integration Tester
Direct testing against NetBox container to validate sync functionality

FRAUD PREVENTION: Direct container inspection and database validation
"""

import os
import sys
import json
import time
import docker
import logging
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

class ContainerIntegrationTester:
    """
    Test sync functionality directly against running NetBox container
    Provides concrete evidence of what's actually happening inside the container
    """
    
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.evidence_dir = Path(f"container_evidence_{self.timestamp}")
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logging()
        self.docker_client = None
        self.netbox_container = None
        
    def _setup_logging(self):
        """Setup logging for container tests"""
        log_file = self.evidence_dir / "container_integration_test.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info("=== CONTAINER INTEGRATION TEST STARTED ===")
        
        return logger
    
    def connect_to_container(self) -> bool:
        """Connect to Docker and find NetBox container"""
        try:
            self.docker_client = docker.from_env()
            
            # Look for NetBox container
            containers = self.docker_client.containers.list()
            
            netbox_candidates = []
            for container in containers:
                if any(keyword in container.name.lower() for keyword in ['netbox', 'hedgehog']):
                    netbox_candidates.append(container)
            
            if not netbox_candidates:
                self.logger.error("No NetBox containers found")
                return False
            
            # Use the first candidate
            self.netbox_container = netbox_candidates[0]
            self.logger.info(f"Connected to container: {self.netbox_container.name}")
            
            # Log container details
            container_info = {
                'name': self.netbox_container.name,
                'id': self.netbox_container.id[:12],
                'status': self.netbox_container.status,
                'image': str(self.netbox_container.image),
                'ports': self.netbox_container.ports
            }
            
            with open(self.evidence_dir / "container_info.json", 'w') as f:
                json.dump(container_info, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Container connection failed: {e}")
            return False
    
    def execute_container_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Execute command inside NetBox container"""
        if not self.netbox_container:
            return {'error': 'No container connection'}
        
        try:
            self.logger.info(f"Executing in container: {' '.join(command)}")
            
            result = self.netbox_container.exec_run(
                command,
                stdout=True,
                stderr=True,
                timeout=timeout
            )
            
            return {
                'command': ' '.join(command),
                'exit_code': result.exit_code,
                'stdout': result.output.decode('utf-8') if result.output else '',
                'stderr': '',  # exec_run combines stdout/stderr
                'timestamp': datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Container command failed: {e}")
            return {
                'command': ' '.join(command),
                'error': str(e),
                'timestamp': datetime.datetime.now().isoformat()
            }
    
    def test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity from within container"""
        self.logger.info("Testing database connectivity...")
        
        # Test Django database connection
        django_test = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'shell', '-c',
            'from django.db import connection; cursor = connection.cursor(); cursor.execute("SELECT 1"); print("Database OK")'
        ])
        
        # Test direct fabric query
        fabric_test = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'shell', '-c',
            '''
from netbox_hedgehog.models import Fabric
fabrics = Fabric.objects.filter(sync_enabled=True)
print(f"Sync-enabled fabrics: {fabrics.count()}")
for f in fabrics:
    print(f"Fabric {f.id}: {f.name}, interval={f.sync_interval}, last_sync={f.last_sync}")
'''
        ])
        
        return {
            'django_database_test': django_test,
            'fabric_query_test': fabric_test,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    def test_django_management_commands(self) -> Dict[str, Any]:
        """Test Django management commands inside container"""
        self.logger.info("Testing Django management commands...")
        
        tests = {}
        
        # Test help command
        tests['help_test'] = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'help'
        ])
        
        # Test hedgehog_sync command help
        tests['hedgehog_sync_help'] = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'help', 'hedgehog_sync'
        ])
        
        # Test dry-run sync (if available)
        tests['sync_dry_run'] = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'hedgehog_sync', '--dry-run'
        ], timeout=60)
        
        return tests
    
    def test_rq_worker_status(self) -> Dict[str, Any]:
        """Test RQ worker status and job queue"""
        self.logger.info("Testing RQ worker status...")
        
        tests = {}
        
        # Check RQ processes
        tests['rq_processes'] = self.execute_container_command([
            'ps', 'aux'
        ])
        
        # Test RQ info command (if available)
        tests['rq_info'] = self.execute_container_command([
            'python', '-c', '''
import redis
try:
    r = redis.Redis(host="redis", port=6379, db=0)
    print(f"Redis ping: {r.ping()}")
    print(f"Redis info: {r.info()}")
except Exception as e:
    print(f"Redis error: {e}")
'''
        ])
        
        # Check for RQ worker processes
        tests['rq_worker_check'] = self.execute_container_command([
            'python', '-c', '''
from rq import Worker
import redis
try:
    r = redis.Redis(host="redis", port=6379, db=0)
    workers = Worker.all(connection=r)
    print(f"Active workers: {len(workers)}")
    for worker in workers:
        print(f"Worker: {worker.name}, state: {worker.get_state()}")
except Exception as e:
    print(f"RQ worker check error: {e}")
'''
        ])
        
        return tests
    
    def test_file_system_access(self) -> Dict[str, Any]:
        """Test file system access and log files"""
        self.logger.info("Testing file system access...")
        
        tests = {}
        
        # Check NetBox directory structure
        tests['netbox_structure'] = self.execute_container_command([
            'find', '/opt/netbox', '-name', '*hedgehog*', '-type', 'f'
        ])
        
        # Check for log files
        tests['log_files'] = self.execute_container_command([
            'find', '/opt/netbox', '-name', '*.log', '-type', 'f'
        ])
        
        # Check if periodic sync script exists
        tests['periodic_sync_files'] = self.execute_container_command([
            'find', '/opt/netbox', '-name', '*periodic*', '-o', '-name', '*sync*', '-type', 'f'
        ])
        
        # Check Python path and installed packages
        tests['python_packages'] = self.execute_container_command([
            'python', '-c', 'import sys; print("\\n".join(sys.path))'
        ])
        
        tests['hedgehog_import'] = self.execute_container_command([
            'python', '-c', 'import netbox_hedgehog; print("Hedgehog plugin imported successfully")'
        ])
        
        return tests
    
    def monitor_container_activity(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """Monitor container activity for sync behavior"""
        self.logger.info(f"Monitoring container activity for {duration_minutes} minutes...")
        
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)
        
        activity_log = []
        
        while datetime.datetime.now() < end_time:
            check_time = datetime.datetime.now()
            
            # Get current processes
            processes = self.execute_container_command(['ps', 'aux'])
            
            # Get database state
            db_state = self.execute_container_command([
                'python', '/opt/netbox/manage.py', 'shell', '-c',
                '''
from netbox_hedgehog.models import Fabric
import json
fabrics = []
for f in Fabric.objects.filter(sync_enabled=True):
    fabrics.append({
        "id": f.id,
        "name": f.name,
        "sync_enabled": f.sync_enabled,
        "sync_interval": f.sync_interval,
        "last_sync": f.last_sync.isoformat() if f.last_sync else None,
        "last_updated": f.last_updated.isoformat() if f.last_updated else None
    })
print(json.dumps(fabrics, indent=2))
'''
            ])
            
            activity_point = {
                'timestamp': check_time.isoformat(),
                'processes': processes,
                'database_state': db_state
            }
            
            activity_log.append(activity_point)
            
            # Wait 30 seconds between checks
            if datetime.datetime.now() < end_time:
                time.sleep(30)
        
        return {
            'monitoring_duration_minutes': duration_minutes,
            'total_checks': len(activity_log),
            'activity_log': activity_log,
            'start_time': start_time.isoformat(),
            'end_time': datetime.datetime.now().isoformat()
        }
    
    def test_manual_sync_execution(self) -> Dict[str, Any]:
        """Test manual sync execution to verify the process works"""
        self.logger.info("Testing manual sync execution...")
        
        # Get pre-sync state
        pre_sync_state = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'shell', '-c',
            '''
from netbox_hedgehog.models import Fabric
import json
fabrics = []
for f in Fabric.objects.filter(sync_enabled=True):
    fabrics.append({
        "id": f.id,
        "name": f.name,
        "last_sync": f.last_sync.isoformat() if f.last_sync else None
    })
print("PRE_SYNC:", json.dumps(fabrics))
'''
        ])
        
        # Attempt manual sync
        manual_sync = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'hedgehog_sync'
        ], timeout=120)
        
        # Wait a moment then get post-sync state
        time.sleep(5)
        
        post_sync_state = self.execute_container_command([
            'python', '/opt/netbox/manage.py', 'shell', '-c',
            '''
from netbox_hedgehog.models import Fabric
import json
fabrics = []
for f in Fabric.objects.filter(sync_enabled=True):
    fabrics.append({
        "id": f.id,
        "name": f.name,
        "last_sync": f.last_sync.isoformat() if f.last_sync else None
    })
print("POST_SYNC:", json.dumps(fabrics))
'''
        ])
        
        return {
            'pre_sync_state': pre_sync_state,
            'manual_sync_execution': manual_sync,
            'post_sync_state': post_sync_state,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    def run_comprehensive_container_test(self) -> Dict[str, Any]:
        """Run comprehensive container integration test"""
        self.logger.info("=== STARTING COMPREHENSIVE CONTAINER TEST ===")
        
        if not self.connect_to_container():
            return {'error': 'Could not connect to NetBox container'}
        
        test_results = {
            'test_metadata': {
                'start_time': datetime.datetime.now().isoformat(),
                'container_name': self.netbox_container.name,
                'container_id': self.netbox_container.id[:12]
            }
        }
        
        # Run all tests
        test_results['database_connectivity'] = self.test_database_connectivity()
        test_results['django_commands'] = self.test_django_management_commands()
        test_results['rq_worker_status'] = self.test_rq_worker_status()
        test_results['file_system_access'] = self.test_file_system_access()
        test_results['manual_sync_test'] = self.test_manual_sync_execution()
        
        # Monitor for sync activity
        test_results['activity_monitoring'] = self.monitor_container_activity(duration_minutes=3)
        
        test_results['test_metadata']['end_time'] = datetime.datetime.now().isoformat()
        
        # Save comprehensive results
        results_file = self.evidence_dir / "comprehensive_container_test_results.json"
        with open(results_file, 'w') as f:
            json.dump(test_results, f, indent=2)
        
        self.logger.info(f"Comprehensive test results saved to: {results_file}")
        
        return test_results
    
    def generate_container_evidence_summary(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of container evidence"""
        summary = {
            'timestamp': datetime.datetime.now().isoformat(),
            'evidence_type': 'container_integration',
            'container_accessible': 'container_name' in test_results.get('test_metadata', {}),
            'database_working': False,
            'django_commands_available': False,
            'manual_sync_works': False,
            'periodic_sync_evidence': False,
            'critical_findings': []
        }
        
        # Analyze database connectivity
        db_test = test_results.get('database_connectivity', {})
        django_db = db_test.get('django_database_test', {})
        if django_db.get('exit_code') == 0 and 'Database OK' in django_db.get('stdout', ''):
            summary['database_working'] = True
        
        # Analyze Django commands
        django_test = test_results.get('django_commands', {})
        hedgehog_help = django_test.get('hedgehog_sync_help', {})
        if hedgehog_help.get('exit_code') == 0:
            summary['django_commands_available'] = True
            summary['critical_findings'].append("✅ hedgehog_sync Django command is available")
        else:
            summary['critical_findings'].append("❌ hedgehog_sync Django command not found")
        
        # Analyze manual sync test
        manual_test = test_results.get('manual_sync_test', {})
        manual_exec = manual_test.get('manual_sync_execution', {})
        if manual_exec.get('exit_code') == 0:
            summary['manual_sync_works'] = True
            summary['critical_findings'].append("✅ Manual sync execution succeeded")
        else:
            summary['critical_findings'].append("❌ Manual sync execution failed")
        
        # Analyze activity monitoring
        activity = test_results.get('activity_monitoring', {})
        if activity and len(activity.get('activity_log', [])) > 0:
            summary['critical_findings'].append(f"📊 Monitored container for {activity.get('monitoring_duration_minutes', 0)} minutes")
        
        return summary


if __name__ == '__main__':
    tester = ContainerIntegrationTester()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'full':
        # Run comprehensive test
        results = tester.run_comprehensive_container_test()
        summary = tester.generate_container_evidence_summary(results)
        
        print("\n=== CONTAINER INTEGRATION TEST SUMMARY ===")
        print(json.dumps(summary, indent=2))
    else:
        print("Container Integration Tester")
        print("Usage:")
        print("  python container_integration_tester.py full   # Run comprehensive container test")