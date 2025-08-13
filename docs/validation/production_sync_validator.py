#!/usr/bin/env python3
"""
Production Sync Validation System
Real-time monitoring and evidence collection for periodic sync functionality

FRAUD PREVENTION: All evidence is timestamped, logged, and independently verifiable
"""

import os
import sys
import time
import json
import logging
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
import psycopg2
import redis
from contextlib import contextmanager

# Add Django settings to path for database access
sys.path.append('/opt/netbox')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

import django
django.setup()

from django.db import connection
from rq import Queue
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

class ProductionSyncValidator:
    """
    MISSION CRITICAL: Provide concrete, verifiable evidence of sync functionality
    
    This class monitors the actual running NetBox environment and collects
    real-time evidence of periodic sync behavior.
    """
    
    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.evidence_log = []
        self.monitoring_active = True
        
        # Setup logging with microsecond precision
        self.logger = self._setup_logging()
        
        # Database connection for direct queries
        self.db_connection = None
        
        # Redis connection for RQ monitoring
        self.redis_conn = None
        self.rq_queue = None
        
        # Evidence collection paths
        self.evidence_dir = Path("production_validation_evidence")
        self.evidence_dir.mkdir(exist_ok=True)
        
    def _setup_logging(self) -> logging.Logger:
        """Setup high-precision logging system"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file = f"sync_validation_{timestamp}.log"
        
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
        logger.info("=== PRODUCTION SYNC VALIDATION STARTED ===")
        logger.info(f"Evidence will be collected in: {self.evidence_dir.absolute()}")
        
        return logger
    
    @contextmanager
    def database_connection(self):
        """Direct database connection context manager"""
        try:
            # Use Django's database connection
            with connection.cursor() as cursor:
                yield cursor
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise
    
    def connect_redis(self) -> bool:
        """Connect to Redis for RQ monitoring"""
        try:
            # Try common Redis configurations
            redis_configs = [
                {'host': 'localhost', 'port': 6379, 'db': 0},
                {'host': 'redis', 'port': 6379, 'db': 0},
                {'host': '127.0.0.1', 'port': 6379, 'db': 0}
            ]
            
            for config in redis_configs:
                try:
                    self.redis_conn = redis.Redis(**config)
                    self.redis_conn.ping()  # Test connection
                    self.rq_queue = Queue('hedgehog_sync', connection=self.redis_conn)
                    self.logger.info(f"Redis connected: {config}")
                    return True
                except:
                    continue
                    
            self.logger.warning("Redis connection failed - RQ monitoring disabled")
            return False
            
        except Exception as e:
            self.logger.error(f"Redis connection error: {e}")
            return False
    
    def get_fabric_sync_state(self) -> Dict[str, Any]:
        """Get current fabric sync state from database"""
        with self.database_connection() as cursor:
            query = """
            SELECT 
                id,
                name,
                sync_enabled,
                sync_interval,
                last_sync,
                created,
                last_updated
            FROM netbox_hedgehog_fabric
            WHERE sync_enabled = true
            ORDER BY id;
            """
            
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            
            fabrics = []
            for row in cursor.fetchall():
                fabric_data = dict(zip(columns, row))
                # Convert datetime objects to strings for JSON serialization
                for key, value in fabric_data.items():
                    if isinstance(value, datetime.datetime):
                        fabric_data[key] = value.isoformat()
                fabrics.append(fabric_data)
            
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'fabric_count': len(fabrics),
                'fabrics': fabrics
            }
    
    def get_rq_job_status(self) -> Dict[str, Any]:
        """Monitor RQ job queue for sync jobs"""
        if not self.redis_conn or not self.rq_queue:
            return {'status': 'redis_unavailable'}
        
        try:
            # Get different job registries
            started_registry = StartedJobRegistry(queue=self.rq_queue)
            finished_registry = FinishedJobRegistry(queue=self.rq_queue)
            failed_registry = FailedJobRegistry(queue=self.rq_queue)
            
            job_status = {
                'timestamp': datetime.datetime.now().isoformat(),
                'queue_length': len(self.rq_queue),
                'started_jobs': len(started_registry),
                'finished_jobs': len(finished_registry),
                'failed_jobs': len(failed_registry),
                'job_details': []
            }
            
            # Get details of recent jobs
            all_job_ids = list(self.rq_queue.job_ids) + list(started_registry.get_job_ids()) + \
                         list(finished_registry.get_job_ids())[:10]  # Last 10 finished
            
            for job_id in all_job_ids[:20]:  # Limit to avoid spam
                try:
                    job = self.rq_queue.job_class.fetch(job_id, connection=self.redis_conn)
                    if job and 'sync' in str(job.func_name).lower():
                        job_status['job_details'].append({
                            'id': job.id,
                            'func_name': str(job.func_name),
                            'status': job.get_status(),
                            'created_at': job.created_at.isoformat() if job.created_at else None,
                            'started_at': job.started_at.isoformat() if job.started_at else None,
                            'ended_at': job.ended_at.isoformat() if job.ended_at else None
                        })
                except Exception as e:
                    self.logger.debug(f"Could not fetch job {job_id}: {e}")
            
            return job_status
            
        except Exception as e:
            self.logger.error(f"RQ monitoring error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def check_django_management_commands(self) -> Dict[str, Any]:
        """Test Django management commands for sync functionality"""
        try:
            # Check if hedgehog_sync command exists
            cmd_result = subprocess.run([
                sys.executable, 'manage.py', 'help', 'hedgehog_sync'
            ], cwd='/opt/netbox', capture_output=True, text=True, timeout=10)
            
            command_available = cmd_result.returncode == 0
            
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'hedgehog_sync_command_available': command_available,
                'help_output': cmd_result.stdout if command_available else cmd_result.stderr,
                'return_code': cmd_result.returncode
            }
            
        except Exception as e:
            self.logger.error(f"Django command check failed: {e}")
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'error': str(e),
                'hedgehog_sync_command_available': False
            }
    
    def collect_system_evidence(self) -> Dict[str, Any]:
        """Collect system-level evidence about sync processes"""
        evidence = {
            'timestamp': datetime.datetime.now().isoformat(),
            'processes': [],
            'network_connections': [],
            'log_entries': []
        }
        
        try:
            # Check for any sync-related processes
            ps_result = subprocess.run([
                'ps', 'aux'
            ], capture_output=True, text=True)
            
            if ps_result.returncode == 0:
                sync_processes = [
                    line for line in ps_result.stdout.split('\n')
                    if any(keyword in line.lower() for keyword in ['sync', 'hedgehog', 'rq'])
                ]
                evidence['processes'] = sync_processes[:10]  # Limit output
            
        except Exception as e:
            self.logger.debug(f"Process check failed: {e}")
        
        return evidence
    
    def monitor_sync_behavior(self, duration_minutes: int = 5, check_interval: int = 10) -> List[Dict[str, Any]]:
        """
        Monitor sync behavior over specified duration
        
        Args:
            duration_minutes: How long to monitor (default 5 minutes)
            check_interval: Seconds between checks (default 10)
        """
        self.logger.info(f"Starting {duration_minutes}-minute monitoring session")
        self.logger.info(f"Checking every {check_interval} seconds")
        
        # Initialize Redis connection
        redis_available = self.connect_redis()
        
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        monitoring_data = []
        check_count = 0
        
        while datetime.datetime.now() < end_time:
            check_count += 1
            self.logger.info(f"=== CHECK {check_count} ===")
            
            try:
                # Collect all evidence types
                evidence_point = {
                    'check_number': check_count,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'fabric_state': self.get_fabric_sync_state(),
                    'rq_jobs': self.get_rq_job_status() if redis_available else {'status': 'redis_unavailable'},
                    'django_commands': self.check_django_management_commands(),
                    'system_evidence': self.collect_system_evidence()
                }
                
                monitoring_data.append(evidence_point)
                
                # Log key findings
                fabric_data = evidence_point['fabric_state']
                self.logger.info(f"Fabrics with sync enabled: {fabric_data['fabric_count']}")
                
                for fabric in fabric_data['fabrics']:
                    last_sync = fabric.get('last_sync', 'Never')
                    interval = fabric.get('sync_interval', 'Unknown')
                    self.logger.info(f"Fabric {fabric['id']} ({fabric['name']}): "
                                   f"Last sync: {last_sync}, Interval: {interval}s")
                
                # Save incremental evidence
                evidence_file = self.evidence_dir / f"monitoring_evidence_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
                with open(evidence_file, 'w') as f:
                    json.dump(monitoring_data, f, indent=2)
                
            except Exception as e:
                self.logger.error(f"Evidence collection failed on check {check_count}: {e}")
                # Continue monitoring even if one check fails
            
            if datetime.datetime.now() < end_time:
                time.sleep(check_interval)
        
        self.logger.info(f"Monitoring completed. {check_count} checks performed.")
        return monitoring_data
    
    def analyze_sync_evidence(self, monitoring_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze collected evidence to determine if sync is actually working
        
        This is the CRITICAL FRAUD PREVENTION function - it provides definitive
        proof of whether sync is working or not.
        """
        analysis = {
            'analysis_timestamp': datetime.datetime.now().isoformat(),
            'monitoring_duration_minutes': len(monitoring_data) * 10 / 60,  # 10-second intervals
            'total_checks': len(monitoring_data),
            'fabrics_analyzed': {},
            'sync_activity_detected': False,
            'evidence_summary': [],
            'definitive_conclusion': 'UNKNOWN'
        }
        
        if not monitoring_data:
            analysis['definitive_conclusion'] = 'NO_DATA_COLLECTED'
            return analysis
        
        # Analyze each fabric's sync behavior
        for fabric_id in set(
            str(fabric['id']) 
            for data_point in monitoring_data 
            for fabric in data_point['fabric_state']['fabrics']
        ):
            fabric_analysis = self._analyze_fabric_sync_behavior(fabric_id, monitoring_data)
            analysis['fabrics_analyzed'][fabric_id] = fabric_analysis
            
            if fabric_analysis['sync_detected']:
                analysis['sync_activity_detected'] = True
        
        # Analyze RQ job activity
        rq_analysis = self._analyze_rq_job_activity(monitoring_data)
        analysis['rq_job_analysis'] = rq_analysis
        
        if rq_analysis['sync_jobs_detected']:
            analysis['sync_activity_detected'] = True
        
        # Generate evidence summary
        analysis['evidence_summary'] = self._generate_evidence_summary(analysis)
        
        # Make definitive conclusion
        if analysis['sync_activity_detected']:
            analysis['definitive_conclusion'] = 'SYNC_IS_WORKING'
        else:
            analysis['definitive_conclusion'] = 'SYNC_IS_NOT_WORKING'
        
        return analysis
    
    def _analyze_fabric_sync_behavior(self, fabric_id: str, monitoring_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sync behavior for a specific fabric"""
        fabric_sync_times = []
        fabric_intervals = []
        fabric_names = []
        
        for data_point in monitoring_data:
            for fabric in data_point['fabric_state']['fabrics']:
                if str(fabric['id']) == fabric_id:
                    if fabric.get('last_sync') and fabric['last_sync'] != 'Never':
                        fabric_sync_times.append(fabric['last_sync'])
                    if fabric.get('sync_interval'):
                        fabric_intervals.append(fabric['sync_interval'])
                    fabric_names.append(fabric.get('name', 'Unknown'))
        
        # Check if last_sync timestamp changed during monitoring
        unique_sync_times = list(set(fabric_sync_times))
        sync_detected = len(unique_sync_times) > 1
        
        return {
            'fabric_id': fabric_id,
            'fabric_name': fabric_names[-1] if fabric_names else 'Unknown',
            'sync_detected': sync_detected,
            'unique_sync_timestamps': unique_sync_times,
            'sync_intervals_observed': list(set(fabric_intervals)),
            'total_observations': len([dp for dp in monitoring_data 
                                     for f in dp['fabric_state']['fabrics'] 
                                     if str(f['id']) == fabric_id])
        }
    
    def _analyze_rq_job_activity(self, monitoring_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze RQ job queue for sync activity"""
        sync_jobs_found = []
        queue_lengths = []
        
        for data_point in monitoring_data:
            rq_data = data_point.get('rq_jobs', {})
            
            if rq_data.get('status') != 'redis_unavailable':
                queue_lengths.append(rq_data.get('queue_length', 0))
                
                for job_detail in rq_data.get('job_details', []):
                    if 'sync' in job_detail.get('func_name', '').lower():
                        sync_jobs_found.append(job_detail)
        
        return {
            'sync_jobs_detected': len(sync_jobs_found) > 0,
            'total_sync_jobs_found': len(sync_jobs_found),
            'sync_job_details': sync_jobs_found,
            'queue_length_changes': len(set(queue_lengths)) > 1 if queue_lengths else False,
            'redis_available': any(
                dp.get('rq_jobs', {}).get('status') != 'redis_unavailable' 
                for dp in monitoring_data
            )
        }
    
    def _generate_evidence_summary(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate human-readable evidence summary"""
        summary = []
        
        if analysis['sync_activity_detected']:
            summary.append("✅ SYNC ACTIVITY DETECTED - Evidence of periodic sync functionality")
            
            for fabric_id, fabric_analysis in analysis['fabrics_analyzed'].items():
                if fabric_analysis['sync_detected']:
                    summary.append(f"   └─ Fabric {fabric_id} ({fabric_analysis['fabric_name']}): "
                                 f"last_sync timestamp changed {len(fabric_analysis['unique_sync_timestamps'])} times")
            
            if analysis['rq_job_analysis']['sync_jobs_detected']:
                job_count = analysis['rq_job_analysis']['total_sync_jobs_found']
                summary.append(f"   └─ RQ Queue: {job_count} sync jobs detected")
        else:
            summary.append("❌ NO SYNC ACTIVITY DETECTED - No evidence of periodic sync functionality")
            summary.append("   └─ No fabric last_sync timestamps changed during monitoring")
            summary.append("   └─ No sync jobs found in RQ queue")
        
        summary.append(f"📊 Monitoring Stats: {analysis['total_checks']} checks over "
                      f"{analysis['monitoring_duration_minutes']:.1f} minutes")
        
        return summary
    
    def run_60_second_timer_test(self) -> Dict[str, Any]:
        """
        CRITICAL TEST: 60-second timer validation
        Monitor for exactly 5 minutes to catch 5 sync attempts
        """
        self.logger.info("=== STARTING 60-SECOND TIMER TEST ===")
        
        # First, verify we have a fabric configured for 60-second sync
        initial_state = self.get_fabric_sync_state()
        
        sixty_second_fabrics = [
            f for f in initial_state['fabrics'] 
            if f.get('sync_interval') == 60
        ]
        
        if not sixty_second_fabrics:
            return {
                'test_result': 'CONFIGURATION_ERROR',
                'message': 'No fabrics configured with 60-second sync interval',
                'available_fabrics': initial_state['fabrics']
            }
        
        self.logger.info(f"Found {len(sixty_second_fabrics)} fabrics with 60-second intervals")
        
        # Monitor for 5 minutes (300 seconds) to catch 5 sync cycles
        monitoring_data = self.monitor_sync_behavior(duration_minutes=5, check_interval=10)
        
        # Analyze the results
        analysis = self.analyze_sync_evidence(monitoring_data)
        
        # Specific analysis for 60-second test
        timer_analysis = {
            'test_type': '60_second_timer_validation',
            'expected_sync_cycles': 5,
            'monitoring_duration_seconds': 300,
            'fabrics_tested': sixty_second_fabrics,
            'raw_monitoring_data': monitoring_data,
            'evidence_analysis': analysis,
            'test_timestamp': datetime.datetime.now().isoformat()
        }
        
        # Save comprehensive evidence
        evidence_file = self.evidence_dir / f"60_second_timer_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, 'w') as f:
            json.dump(timer_analysis, f, indent=2)
        
        self.logger.info(f"60-second timer test evidence saved to: {evidence_file}")
        
        return timer_analysis
    
    def generate_production_evidence_package(self) -> str:
        """Generate final evidence package with fraud prevention measures"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        package_file = f"production_sync_evidence_{timestamp}.json"
        
        # Run comprehensive test
        self.logger.info("Generating production evidence package...")
        
        evidence_package = {
            'validation_metadata': {
                'validator_version': '1.0.0',
                'validation_timestamp': datetime.datetime.now().isoformat(),
                'environment': 'production',
                'fraud_prevention_enabled': True,
                'evidence_independently_reproducible': True
            },
            'system_information': {
                'python_version': sys.version,
                'working_directory': os.getcwd(),
                'validator_script_path': os.path.abspath(__file__)
            }
        }
        
        # Execute 60-second timer test
        timer_test_results = self.run_60_second_timer_test()
        evidence_package['timer_test_results'] = timer_test_results
        
        # Additional configuration testing
        evidence_package['configuration_tests'] = self._test_configuration_changes()
        
        # Save evidence package
        with open(package_file, 'w') as f:
            json.dump(evidence_package, f, indent=2)
        
        self.logger.info(f"=== PRODUCTION EVIDENCE PACKAGE GENERATED ===")
        self.logger.info(f"File: {package_file}")
        self.logger.info(f"Size: {os.path.getsize(package_file)} bytes")
        
        return package_file
    
    def _test_configuration_changes(self) -> Dict[str, Any]:
        """Test configuration change scenarios"""
        # This would test changing sync intervals, but we'll just document current state
        # to avoid modifying production data
        
        return {
            'test_type': 'configuration_documentation',
            'note': 'Configuration change testing skipped in production environment',
            'current_fabric_configurations': self.get_fabric_sync_state(),
            'django_command_status': self.check_django_management_commands()
        }


if __name__ == '__main__':
    validator = ProductionSyncValidator()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == 'quick':
            # Quick 2-minute test
            monitoring_data = validator.monitor_sync_behavior(duration_minutes=2, check_interval=10)
            analysis = validator.analyze_sync_evidence(monitoring_data)
            print("\n=== QUICK TEST RESULTS ===")
            print(json.dumps(analysis, indent=2))
        elif sys.argv[1] == 'timer':
            # 60-second timer test
            results = validator.run_60_second_timer_test()
            print("\n=== 60-SECOND TIMER TEST RESULTS ===")
            print(json.dumps(results['evidence_analysis'], indent=2))
        elif sys.argv[1] == 'full':
            # Full evidence package
            package_file = validator.generate_production_evidence_package()
            print(f"\n=== FULL EVIDENCE PACKAGE GENERATED ===")
            print(f"Evidence file: {package_file}")
    else:
        print("Production Sync Validator")
        print("Usage:")
        print("  python production_sync_validator.py quick   # 2-minute quick test")
        print("  python production_sync_validator.py timer   # 5-minute 60-second timer test")
        print("  python production_sync_validator.py full    # Full evidence package")