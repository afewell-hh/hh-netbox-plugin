#!/usr/bin/env python3
"""
Environment Inspector
Comprehensive inspection of the production environment

FRAUD PREVENTION: Document exactly what's available in the environment
"""

import os
import sys
import json
import logging
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Any

class EnvironmentInspector:
    """
    Comprehensive environment inspection to understand what's available
    """
    
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.evidence_dir = Path(f"environment_inspection_{self.timestamp}")
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging"""
        log_file = self.evidence_dir / f"environment_inspection.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info("=== ENVIRONMENT INSPECTION STARTED ===")
        
        return logger
    
    def run_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run command and capture output"""
        try:
            self.logger.info(f"Running: {' '.join(command)}")
            
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
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'command': ' '.join(command),
                'error': 'Command timed out',
                'success': False
            }
        except Exception as e:
            return {
                'command': ' '.join(command),
                'error': str(e),
                'success': False
            }
    
    def inspect_docker_environment(self) -> Dict[str, Any]:
        """Inspect Docker environment"""
        inspection = {
            'docker_available': False,
            'docker_version': None,
            'containers': [],
            'images': [],
            'compose_files': []
        }
        
        # Check if Docker is available
        docker_version = self.run_command(['docker', '--version'])
        if docker_version['success']:
            inspection['docker_available'] = True
            inspection['docker_version'] = docker_version['stdout'].strip()
        else:
            self.logger.warning("Docker not available")
            return inspection
        
        # List running containers
        containers = self.run_command(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'])
        if containers['success']:
            inspection['containers_raw'] = containers['stdout']
        
        # List all containers
        all_containers = self.run_command(['docker', 'ps', '-a', '--format', 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'])
        if all_containers['success']:
            inspection['all_containers_raw'] = all_containers['stdout']
        
        # List images
        images = self.run_command(['docker', 'images'])
        if images['success']:
            inspection['images_raw'] = images['stdout']
        
        # Look for docker-compose files
        compose_search = self.run_command(['find', '.', '-name', 'docker-compose*.yml', '-o', '-name', 'docker-compose*.yaml'])
        if compose_search['success']:
            inspection['compose_files'] = compose_search['stdout'].strip().split('\n')
        
        return inspection
    
    def inspect_database_environment(self) -> Dict[str, Any]:
        """Inspect database-related environment"""
        inspection = {
            'postgres_processes': [],
            'postgres_systemctl': None,
            'database_files': [],
            'database_env_vars': {}
        }
        
        # Check PostgreSQL processes
        postgres_ps = self.run_command(['ps', 'aux'])
        if postgres_ps['success']:
            postgres_lines = [line for line in postgres_ps['stdout'].split('\n') 
                             if 'postgres' in line.lower()]
            inspection['postgres_processes'] = postgres_lines
        
        # Check PostgreSQL service
        postgres_status = self.run_command(['systemctl', 'status', 'postgresql'])
        inspection['postgres_systemctl'] = postgres_status
        
        # Look for database files
        db_search = self.run_command(['find', '/var/lib', '-name', '*postgres*', '-type', 'd', '2>/dev/null'])
        if db_search['success']:
            inspection['database_files'] = db_search['stdout'].strip().split('\n')
        
        # Check environment variables
        for var in ['DATABASE_URL', 'POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']:
            if var in os.environ:
                inspection['database_env_vars'][var] = os.environ[var]
        
        return inspection
    
    def inspect_netbox_environment(self) -> Dict[str, Any]:
        """Inspect NetBox-related environment"""
        inspection = {
            'netbox_processes': [],
            'python_processes': [],
            'django_files': [],
            'hedgehog_files': [],
            'netbox_config': None
        }
        
        # Check NetBox processes
        netbox_ps = self.run_command(['ps', 'aux'])
        if netbox_ps['success']:
            netbox_lines = [line for line in netbox_ps['stdout'].split('\n') 
                           if any(keyword in line.lower() for keyword in ['netbox', 'hedgehog', 'django'])]
            inspection['netbox_processes'] = netbox_lines
        
        # Check Python processes
        python_ps = self.run_command(['ps', 'aux'])
        if python_ps['success']:
            python_lines = [line for line in python_ps['stdout'].split('\n') 
                           if 'python' in line.lower()]
            inspection['python_processes'] = python_lines[:20]  # Limit output
        
        # Look for Django files
        django_search = self.run_command(['find', '.', '-name', 'manage.py', '-o', '-name', 'settings.py'])
        if django_search['success']:
            inspection['django_files'] = django_search['stdout'].strip().split('\n')
        
        # Look for Hedgehog files
        hedgehog_search = self.run_command(['find', '.', '-name', '*hedgehog*', '-type', 'f'])
        if hedgehog_search['success']:
            inspection['hedgehog_files'] = hedgehog_search['stdout'].strip().split('\n')[:50]  # Limit output
        
        # Check for NetBox configuration
        if os.path.exists('/opt/netbox'):
            netbox_config_search = self.run_command(['find', '/opt/netbox', '-name', 'configuration.py'])
            if netbox_config_search['success']:
                inspection['netbox_config'] = netbox_config_search['stdout'].strip()
        
        return inspection
    
    def inspect_network_services(self) -> Dict[str, Any]:
        """Inspect network services"""
        inspection = {
            'listening_ports': [],
            'netstat_output': None,
            'redis_status': None,
            'port_scan_results': {}
        }
        
        # Check listening ports
        netstat = self.run_command(['netstat', '-tlnp'])
        if netstat['success']:
            inspection['netstat_output'] = netstat['stdout']
            # Extract listening ports
            for line in netstat['stdout'].split('\n'):
                if 'LISTEN' in line:
                    inspection['listening_ports'].append(line.strip())
        else:
            # Try ss command as alternative
            ss = self.run_command(['ss', '-tlnp'])
            if ss['success']:
                inspection['ss_output'] = ss['stdout']
        
        # Check Redis
        redis_status = self.run_command(['systemctl', 'status', 'redis'])
        inspection['redis_status'] = redis_status
        
        # Quick port checks for common services
        common_ports = [5432, 6379, 8000, 8080, 443, 80]
        for port in common_ports:
            port_check = self.run_command(['nc', '-z', 'localhost', str(port)], timeout=5)
            inspection['port_scan_results'][port] = port_check['success']
        
        return inspection
    
    def inspect_file_system(self) -> Dict[str, Any]:
        """Inspect relevant file system locations"""
        inspection = {
            'current_directory': os.getcwd(),
            'directory_contents': [],
            'opt_contents': [],
            'var_log_contents': [],
            'home_contents': []
        }
        
        # Current directory
        ls_current = self.run_command(['ls', '-la', '.'])
        if ls_current['success']:
            inspection['directory_contents'] = ls_current['stdout']
        
        # /opt directory (common for NetBox)
        if os.path.exists('/opt'):
            ls_opt = self.run_command(['ls', '-la', '/opt'])
            if ls_opt['success']:
                inspection['opt_contents'] = ls_opt['stdout']
        
        # Log directories
        if os.path.exists('/var/log'):
            ls_logs = self.run_command(['find', '/var/log', '-name', '*netbox*', '-o', '-name', '*django*', '-o', '-name', '*hedgehog*'])
            if ls_logs['success']:
                inspection['log_files'] = ls_logs['stdout']
        
        return inspection
    
    def run_comprehensive_inspection(self) -> Dict[str, Any]:
        """Run comprehensive environment inspection"""
        self.logger.info("Starting comprehensive environment inspection...")
        
        inspection_results = {
            'inspection_metadata': {
                'timestamp': datetime.datetime.now().isoformat(),
                'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
                'working_directory': os.getcwd(),
                'python_version': sys.version
            }
        }
        
        # Run all inspections
        self.logger.info("Inspecting Docker environment...")
        inspection_results['docker_environment'] = self.inspect_docker_environment()
        
        self.logger.info("Inspecting database environment...")
        inspection_results['database_environment'] = self.inspect_database_environment()
        
        self.logger.info("Inspecting NetBox environment...")
        inspection_results['netbox_environment'] = self.inspect_netbox_environment()
        
        self.logger.info("Inspecting network services...")
        inspection_results['network_services'] = self.inspect_network_services()
        
        self.logger.info("Inspecting file system...")
        inspection_results['file_system'] = self.inspect_file_system()
        
        # Save comprehensive results
        results_file = self.evidence_dir / f"comprehensive_environment_inspection.json"
        with open(results_file, 'w') as f:
            json.dump(inspection_results, f, indent=2)
        
        self.logger.info(f"Comprehensive inspection completed: {results_file}")
        
        return inspection_results
    
    def generate_environment_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of environment inspection"""
        summary = {
            'timestamp': datetime.datetime.now().isoformat(),
            'environment_type': 'unknown',
            'netbox_deployment_detected': False,
            'database_available': False,
            'sync_infrastructure_available': False,
            'key_findings': []
        }
        
        # Analyze Docker environment
        docker_env = results.get('docker_environment', {})
        if docker_env.get('docker_available'):
            summary['key_findings'].append("✅ Docker is available")
            if docker_env.get('containers_raw'):
                summary['key_findings'].append(f"📦 Docker containers running: {len(docker_env.get('containers_raw', '').split(chr(10)))}")
        else:
            summary['key_findings'].append("❌ Docker not available")
        
        # Analyze database environment
        db_env = results.get('database_environment', {})
        if db_env.get('postgres_processes'):
            summary['database_available'] = True
            summary['key_findings'].append(f"🗄️ PostgreSQL processes found: {len(db_env['postgres_processes'])}")
        
        # Analyze NetBox environment
        netbox_env = results.get('netbox_environment', {})
        if netbox_env.get('hedgehog_files') and len(netbox_env['hedgehog_files']) > 0:
            summary['netbox_deployment_detected'] = True
            summary['key_findings'].append(f"🦔 Hedgehog plugin files found: {len(netbox_env['hedgehog_files'])}")
        
        if netbox_env.get('netbox_processes'):
            summary['key_findings'].append(f"🖥️ NetBox-related processes: {len(netbox_env['netbox_processes'])}")
        
        # Analyze network services
        network_services = results.get('network_services', {})
        port_results = network_services.get('port_scan_results', {})
        
        if port_results.get(5432):  # PostgreSQL
            summary['key_findings'].append("✅ PostgreSQL port (5432) is open")
        if port_results.get(6379):  # Redis
            summary['key_findings'].append("✅ Redis port (6379) is open")
        if port_results.get(8000):  # Django dev server
            summary['key_findings'].append("✅ Django port (8000) is open")
        
        # Determine environment type
        if docker_env.get('docker_available') and summary['netbox_deployment_detected']:
            summary['environment_type'] = 'containerized_netbox'
        elif summary['netbox_deployment_detected'] and summary['database_available']:
            summary['environment_type'] = 'native_netbox'
        elif summary['netbox_deployment_detected']:
            summary['environment_type'] = 'development_netbox'
        else:
            summary['environment_type'] = 'non_netbox'
        
        return summary


if __name__ == '__main__':
    inspector = EnvironmentInspector()
    
    results = inspector.run_comprehensive_inspection()
    summary = inspector.generate_environment_summary(results)
    
    print("\n" + "="*80)
    print("ENVIRONMENT INSPECTION SUMMARY")
    print("="*80)
    
    print(f"Environment type: {summary['environment_type']}")
    print(f"NetBox deployment detected: {summary['netbox_deployment_detected']}")
    print(f"Database available: {summary['database_available']}")
    
    print(f"\nKey findings:")
    for finding in summary['key_findings']:
        print(f"  {finding}")
    
    print(f"\nFull inspection results: {inspector.evidence_dir}")
    
    # Provide recommendations
    print(f"\n📋 RECOMMENDATIONS:")
    if summary['environment_type'] == 'non_netbox':
        print("⚠️  No NetBox deployment detected. Sync validation cannot proceed.")
    elif summary['environment_type'] == 'development_netbox':
        print("🔧 Development environment detected. Start NetBox and database services.")
    elif not summary['database_available']:
        print("🗄️ Database not accessible. Check PostgreSQL configuration.")
    else:
        print("✅ Environment appears suitable for sync validation testing.")
    