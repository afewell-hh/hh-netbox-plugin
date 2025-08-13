#!/usr/bin/env python3
"""
Containerized Production Validator
Specialized validator for containerized NetBox environments

FRAUD PREVENTION: Direct container inspection and HTTP API validation
"""

import os
import sys
import json
import time
import logging
import datetime
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

class ContainerizedProductionValidator:
    """
    Validator for containerized NetBox environments
    Uses HTTP API and container inspection to validate sync functionality
    """
    
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.evidence_dir = Path(f"containerized_validation_{self.timestamp}")
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logging()
        
        # NetBox API endpoints to try
        self.api_endpoints = [
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'http://netbox:8000'
        ]
        
        self.working_endpoint = None
        
    def _setup_logging(self):
        """Setup logging"""
        log_file = self.evidence_dir / f"containerized_validation_{self.timestamp}.log"
        
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
        logger.info("=== CONTAINERIZED PRODUCTION VALIDATION STARTED ===")
        
        return logger
    
    def run_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run shell command and capture output"""
        try:
            self.logger.debug(f"Running: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'command': ' '.join(command),
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'command': ' '.join(command),
                'error': str(e),
                'success': False,
                'timestamp': datetime.datetime.now().isoformat()
            }
    
    def find_netbox_endpoint(self) -> Optional[str]:
        """Find working NetBox API endpoint"""
        self.logger.info("Looking for NetBox API endpoint...")
        
        for endpoint in self.api_endpoints:
            try:
                self.logger.info(f"Trying endpoint: {endpoint}")
                
                response = requests.get(
                    f"{endpoint}/api/",
                    timeout=10,
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code == 200:
                    self.working_endpoint = endpoint
                    self.logger.info(f"✅ Found working endpoint: {endpoint}")
                    return endpoint
                
            except Exception as e:
                self.logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        self.logger.error("❌ No working NetBox API endpoint found")
        return None
    
    def get_fabric_data_via_api(self) -> Dict[str, Any]:
        """Get fabric data via NetBox API"""
        if not self.working_endpoint:
            return {'error': 'No working endpoint available'}
        
        try:
            # Try to get fabric data from API
            # Note: This may require authentication
            api_urls = [
                f"{self.working_endpoint}/api/plugins/netbox-hedgehog/fabrics/",
                f"{self.working_endpoint}/api/plugins/hedgehog/fabrics/",
                f"{self.working_endpoint}/api/dcim/devices/"  # Fallback to devices
            ]
            
            for api_url in api_urls:
                try:
                    self.logger.info(f"Trying API: {api_url}")
                    
                    response = requests.get(
                        api_url,
                        timeout=15,
                        headers={
                            'Accept': 'application/json',
                            'Content-Type': 'application/json'
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        self.logger.info(f"✅ API call successful: {len(data.get('results', []))} items")
                        return {
                            'success': True,
                            'url': api_url,
                            'data': data,
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                    
                    elif response.status_code == 401:
                        self.logger.warning(f"API requires authentication: {api_url}")
                        return {
                            'error': 'Authentication required',
                            'url': api_url,
                            'status_code': 401
                        }
                    
                    else:
                        self.logger.debug(f"API returned {response.status_code}: {api_url}")
                
                except requests.exceptions.ConnectionError:
                    self.logger.debug(f"Connection failed: {api_url}")
                    continue
                except Exception as e:
                    self.logger.debug(f"API call failed: {api_url} - {e}")
                    continue
            
            return {'error': 'All API endpoints failed or require authentication'}
            
        except Exception as e:
            return {'error': f'API call failed: {e}'}
    
    def get_fabric_data_via_django_shell(self) -> Dict[str, Any]:
        """Get fabric data via Django shell command"""
        try:
            django_command = '''
from netbox_hedgehog.models import Fabric
import json
from django.utils import timezone

fabrics = []
for f in Fabric.objects.all():
    fabric_data = {
        "id": f.id,
        "name": f.name,
        "sync_enabled": getattr(f, 'sync_enabled', None),
        "sync_interval": getattr(f, 'sync_interval', None),
        "last_sync": f.last_sync.isoformat() if hasattr(f, 'last_sync') and f.last_sync else None,
        "last_updated": f.last_updated.isoformat() if f.last_updated else None,
        "created": f.created.isoformat() if f.created else None
    }
    fabrics.append(fabric_data)

result = {
    "timestamp": timezone.now().isoformat(),
    "fabric_count": len(fabrics),
    "fabrics": fabrics
}

print("FABRIC_DATA_START")
print(json.dumps(result, indent=2))
print("FABRIC_DATA_END")
'''
            
            # Try to run Django shell command
            shell_result = self.run_command([
                'python3', 'manage.py', 'shell', '-c', django_command
            ], timeout=60)
            
            if shell_result['success']:
                # Extract JSON from output
                stdout = shell_result['stdout']
                start_marker = "FABRIC_DATA_START"
                end_marker = "FABRIC_DATA_END"
                
                start_idx = stdout.find(start_marker)
                end_idx = stdout.find(end_marker)
                
                if start_idx != -1 and end_idx != -1:
                    json_str = stdout[start_idx + len(start_marker):end_idx].strip()
                    try:
                        fabric_data = json.loads(json_str)
                        return {
                            'success': True,
                            'method': 'django_shell',
                            'data': fabric_data,
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                    except json.JSONDecodeError as e:
                        return {
                            'error': f'JSON decode failed: {e}',
                            'raw_output': stdout
                        }
                else:
                    return {
                        'error': 'Could not find data markers in output',
                        'raw_output': stdout
                    }
            else:
                return {
                    'error': 'Django shell command failed',
                    'command_result': shell_result
                }
                
        except Exception as e:
            return {'error': f'Django shell execution failed: {e}'}
    
    def monitor_fabric_changes(self, duration_minutes: int = 5) -> List[Dict[str, Any]]:
        """Monitor fabric changes over time"""
        self.logger.info(f"Monitoring fabric changes for {duration_minutes} minutes...")
        
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        monitoring_data = []
        check_count = 0
        
        while datetime.datetime.now() < end_time:
            check_count += 1
            self.logger.info(f"=== FABRIC MONITORING CHECK {check_count} ===")
            
            # Try Django shell method first (more reliable)
            fabric_data = self.get_fabric_data_via_django_shell()
            
            if not fabric_data.get('success'):
                # Fallback to API method
                fabric_data = self.get_fabric_data_via_api()
            
            evidence_point = {
                'check_number': check_count,
                'timestamp': datetime.datetime.now().isoformat(),
                'fabric_data': fabric_data
            }
            
            monitoring_data.append(evidence_point)
            
            # Log findings
            if fabric_data.get('success') and fabric_data.get('data'):
                data = fabric_data['data']
                fabric_count = data.get('fabric_count', 0)
                self.logger.info(f"Fabrics found: {fabric_count}")
                
                if 'fabrics' in data:
                    for fabric in data['fabrics']:
                        sync_enabled = fabric.get('sync_enabled', 'unknown')
                        last_sync = fabric.get('last_sync', 'Never')
                        interval = fabric.get('sync_interval', 'Unknown')
                        
                        self.logger.info(f"  Fabric {fabric['id']} ({fabric.get('name', 'Unknown')}): "
                                       f"Sync={sync_enabled}, Last={last_sync}, Interval={interval}s")
            else:
                self.logger.warning(f"Check {check_count}: Could not retrieve fabric data")
            
            # Save incremental evidence
            evidence_file = self.evidence_dir / f"monitoring_data_{self.timestamp}.json"
            with open(evidence_file, 'w') as f:
                json.dump(monitoring_data, f, indent=2)
            
            if datetime.datetime.now() < end_time:
                time.sleep(30)  # Check every 30 seconds
        
        return monitoring_data
    
    def check_sync_processes(self) -> Dict[str, Any]:
        """Check for sync-related processes"""
        process_check = {
            'timestamp': datetime.datetime.now().isoformat(),
            'sync_processes': [],
            'rq_processes': [],
            'django_processes': [],
            'celery_processes': []
        }
        
        # Get all processes
        ps_result = self.run_command(['ps', 'aux'])
        
        if ps_result['success']:
            lines = ps_result['stdout'].split('\n')
            
            for line in lines:
                lower_line = line.lower()
                if 'sync' in lower_line:
                    process_check['sync_processes'].append(line.strip())
                if 'rq' in lower_line:
                    process_check['rq_processes'].append(line.strip())
                if 'django' in lower_line:
                    process_check['django_processes'].append(line.strip())
                if 'celery' in lower_line:
                    process_check['celery_processes'].append(line.strip())
        
        return process_check
    
    def test_manual_sync_command(self) -> Dict[str, Any]:
        """Test manual sync command execution"""
        self.logger.info("Testing manual sync command...")
        
        # Get pre-sync state
        pre_sync = self.get_fabric_data_via_django_shell()
        
        # Try manual sync commands
        sync_commands = [
            ['python3', 'manage.py', 'hedgehog_sync'],
            ['python3', 'manage.py', 'sync_fabrics'],
            ['python3', 'manage.py', 'help']  # Just to see available commands
        ]
        
        sync_results = {}
        
        for command in sync_commands:
            command_name = '_'.join(command[2:]) if len(command) > 2 else 'help'
            self.logger.info(f"Trying command: {' '.join(command)}")
            
            result = self.run_command(command, timeout=120)
            sync_results[command_name] = result
            
            if result['success']:
                self.logger.info(f"✅ Command succeeded: {command_name}")
            else:
                self.logger.warning(f"❌ Command failed: {command_name}")
        
        # Wait a moment and get post-sync state
        time.sleep(5)
        post_sync = self.get_fabric_data_via_django_shell()
        
        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'pre_sync_state': pre_sync,
            'sync_command_results': sync_results,
            'post_sync_state': post_sync
        }
    
    def analyze_monitoring_data(self, monitoring_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze monitoring data for sync evidence"""
        analysis = {
            'analysis_timestamp': datetime.datetime.now().isoformat(),
            'total_checks': len(monitoring_data),
            'successful_checks': 0,
            'sync_activity_detected': False,
            'fabric_analysis': {},
            'definitive_conclusion': 'NO_EVIDENCE'
        }
        
        if not monitoring_data:
            return analysis
        
        # Extract fabric data from successful checks
        fabric_timeline = {}
        
        for data_point in monitoring_data:
            fabric_data = data_point.get('fabric_data', {})
            
            if fabric_data.get('success') and 'data' in fabric_data:
                analysis['successful_checks'] += 1
                
                fabrics = fabric_data['data'].get('fabrics', [])
                
                for fabric in fabrics:
                    fabric_id = str(fabric.get('id', 'unknown'))
                    
                    if fabric_id not in fabric_timeline:
                        fabric_timeline[fabric_id] = {
                            'name': fabric.get('name', 'Unknown'),
                            'sync_enabled': fabric.get('sync_enabled'),
                            'sync_interval': fabric.get('sync_interval'),
                            'sync_timestamps': []
                        }
                    
                    last_sync = fabric.get('last_sync')
                    if last_sync and last_sync != 'Never':
                        fabric_timeline[fabric_id]['sync_timestamps'].append({
                            'timestamp': data_point['timestamp'],
                            'last_sync': last_sync
                        })
        
        # Analyze each fabric for sync activity
        for fabric_id, fabric_info in fabric_timeline.items():
            unique_sync_times = list(set([ts['last_sync'] for ts in fabric_info['sync_timestamps']]))
            sync_detected = len(unique_sync_times) > 1
            
            if sync_detected:
                analysis['sync_activity_detected'] = True
            
            analysis['fabric_analysis'][fabric_id] = {
                'fabric_name': fabric_info['name'],
                'sync_enabled': fabric_info['sync_enabled'],
                'sync_interval': fabric_info['sync_interval'],
                'sync_detected': sync_detected,
                'unique_sync_timestamps': unique_sync_times,
                'total_observations': len(fabric_info['sync_timestamps'])
            }
        
        # Make conclusion
        if analysis['sync_activity_detected']:
            analysis['definitive_conclusion'] = 'SYNC_IS_WORKING'
        elif analysis['successful_checks'] == 0:
            analysis['definitive_conclusion'] = 'NO_DATA_AVAILABLE'
        else:
            analysis['definitive_conclusion'] = 'SYNC_IS_NOT_WORKING'
        
        return analysis
    
    def run_comprehensive_validation(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """Run comprehensive containerized validation"""
        self.logger.info("=== STARTING COMPREHENSIVE CONTAINERIZED VALIDATION ===")
        
        validation_results = {
            'validation_metadata': {
                'start_time': datetime.datetime.now().isoformat(),
                'duration_minutes': duration_minutes,
                'validator_type': 'containerized'
            }
        }
        
        # Find NetBox endpoint
        endpoint = self.find_netbox_endpoint()
        validation_results['endpoint_discovery'] = {
            'working_endpoint': endpoint,
            'all_endpoints_tested': self.api_endpoints
        }
        
        # Check processes
        validation_results['process_check'] = self.check_sync_processes()
        
        # Test manual sync command
        validation_results['manual_sync_test'] = self.test_manual_sync_command()
        
        # Monitor fabric changes
        monitoring_data = self.monitor_fabric_changes(duration_minutes)
        validation_results['fabric_monitoring'] = monitoring_data
        
        # Analyze results
        analysis = self.analyze_monitoring_data(monitoring_data)
        validation_results['analysis'] = analysis
        
        validation_results['definitive_conclusion'] = analysis['definitive_conclusion']
        validation_results['validation_metadata']['end_time'] = datetime.datetime.now().isoformat()
        
        # Save results
        results_file = self.evidence_dir / f"comprehensive_validation_results_{self.timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(validation_results, f, indent=2)
        
        self.logger.info(f"Comprehensive validation completed: {results_file}")
        
        return validation_results


if __name__ == '__main__':
    validator = ContainerizedProductionValidator()
    
    duration = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
    
    print(f"Running containerized production validation for {duration} minutes...")
    
    results = validator.run_comprehensive_validation(duration_minutes=duration)
    
    print("\n" + "="*80)
    print("CONTAINERIZED PRODUCTION VALIDATION RESULTS")
    print("="*80)
    
    endpoint_info = results.get('endpoint_discovery', {})
    print(f"NetBox endpoint: {endpoint_info.get('working_endpoint', 'Not found')}")
    
    process_info = results.get('process_check', {})
    print(f"Sync processes: {len(process_info.get('sync_processes', []))}")
    print(f"Django processes: {len(process_info.get('django_processes', []))}")
    print(f"RQ processes: {len(process_info.get('rq_processes', []))}")
    
    analysis = results.get('analysis', {})
    print(f"\nMonitoring checks: {analysis.get('total_checks', 0)}")
    print(f"Successful checks: {analysis.get('successful_checks', 0)}")
    print(f"Sync activity detected: {analysis.get('sync_activity_detected', False)}")
    
    fabric_analysis = analysis.get('fabric_analysis', {})
    for fabric_id, fabric_info in fabric_analysis.items():
        print(f"  Fabric {fabric_id} ({fabric_info.get('fabric_name', 'Unknown')}): "
              f"Enabled={fabric_info.get('sync_enabled')}, "
              f"Sync detected={fabric_info.get('sync_detected')}")
    
    conclusion = results.get('definitive_conclusion', 'UNKNOWN')
    print(f"\n🎯 DEFINITIVE CONCLUSION: {conclusion}")
    
    if conclusion == 'SYNC_IS_WORKING':
        print("✅ EVIDENCE: Periodic sync functionality is WORKING")
    elif conclusion == 'SYNC_IS_NOT_WORKING':
        print("❌ EVIDENCE: Periodic sync functionality is NOT working")
    else:
        print("⚠️  EVIDENCE: Could not determine sync status")
    
    print(f"\nFull results: {validator.evidence_dir}")
    