#!/usr/bin/env python3
"""
Simple Production Validator
Direct database monitoring without Django dependencies

FRAUD PREVENTION: Raw database queries and system monitoring
"""

import os
import sys
import json
import time
import logging
import datetime
import subprocess
import psycopg2
from pathlib import Path
from typing import Dict, List, Any, Optional

class SimpleProductionValidator:
    """
    Simple validator that works directly with database and system monitoring
    No Django dependencies - pure database and system inspection
    """
    
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.evidence_dir = Path(f"simple_validation_{self.timestamp}")
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logging()
        
        # Database connection parameters (try common configurations)
        self.db_configs = [
            {
                'host': 'localhost',
                'port': 5432,
                'database': 'netbox',
                'user': 'netbox',
                'password': 'netbox'
            },
            {
                'host': '127.0.0.1',
                'port': 5432,
                'database': 'netbox',
                'user': 'netbox',
                'password': 'netbox'
            },
            {
                'host': 'postgres',
                'port': 5432,
                'database': 'netbox',
                'user': 'netbox',
                'password': 'netbox'
            }
        ]
        
    def _setup_logging(self):
        """Setup simple logging"""
        log_file = self.evidence_dir / f"simple_validation_{self.timestamp}.log"
        
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
        logger.info("=== SIMPLE PRODUCTION VALIDATION STARTED ===")
        
        return logger
    
    def try_database_connection(self):
        """Try to connect to database with various configurations"""
        for config in self.db_configs:
            try:
                self.logger.info(f"Trying database connection: {config['host']}:{config['port']}")
                
                conn = psycopg2.connect(**config)
                
                # Test the connection
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    result = cursor.fetchone()
                    self.logger.info(f"Database connection successful: {result[0][:50]}...")
                
                return conn
                
            except Exception as e:
                self.logger.debug(f"Database connection failed ({config['host']}:{config['port']}): {e}")
                continue
        
        self.logger.error("All database connection attempts failed")
        return None
    
    def get_fabric_sync_state_direct(self, conn) -> Dict[str, Any]:
        """Get fabric sync state via direct database query"""
        try:
            with conn.cursor() as cursor:
                # Check if the table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'netbox_hedgehog_fabric'
                    );
                """)
                
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    return {
                        'error': 'netbox_hedgehog_fabric table does not exist',
                        'timestamp': datetime.datetime.now().isoformat()
                    }
                
                # Get fabric sync state
                cursor.execute("""
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
                """)
                
                columns = [desc[0] for desc in cursor.description]
                fabrics = []
                
                for row in cursor.fetchall():
                    fabric_data = dict(zip(columns, row))
                    # Convert datetime objects to strings
                    for key, value in fabric_data.items():
                        if isinstance(value, datetime.datetime):
                            fabric_data[key] = value.isoformat()
                        elif isinstance(value, datetime.date):
                            fabric_data[key] = value.isoformat()
                    fabrics.append(fabric_data)
                
                return {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'table_exists': True,
                    'fabric_count': len(fabrics),
                    'fabrics': fabrics
                }
                
        except Exception as e:
            self.logger.error(f"Direct database query failed: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.datetime.now().isoformat()
            }
    
    def check_docker_containers(self) -> Dict[str, Any]:
        """Check Docker containers without docker-py dependency"""
        try:
            # Use docker command line
            result = subprocess.run([
                'docker', 'ps', '--format', 'json'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {
                    'error': 'Docker not available or permission denied',
                    'stderr': result.stderr
                }
            
            containers = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    try:
                        container = json.loads(line)
                        containers.append(container)
                    except json.JSONDecodeError:
                        continue
            
            # Find NetBox-related containers
            netbox_containers = [
                c for c in containers 
                if any(keyword in c.get('Names', '').lower() or keyword in c.get('Image', '').lower()
                      for keyword in ['netbox', 'hedgehog'])
            ]
            
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'total_containers': len(containers),
                'netbox_containers': netbox_containers
            }
            
        except Exception as e:
            return {
                'error': f'Docker check failed: {e}',
                'timestamp': datetime.datetime.now().isoformat()
            }
    
    def check_processes(self) -> Dict[str, Any]:
        """Check for sync-related processes"""
        try:
            # Check all processes
            result = subprocess.run([
                'ps', 'aux'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {'error': 'Process check failed'}
            
            # Filter for potentially relevant processes
            relevant_processes = []
            for line in result.stdout.split('\n'):
                if any(keyword in line.lower() for keyword in 
                      ['hedgehog', 'sync', 'netbox', 'rq', 'redis', 'django', 'python']):
                    relevant_processes.append(line.strip())
            
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'relevant_process_count': len(relevant_processes),
                'processes': relevant_processes[:20]  # Limit output
            }
            
        except Exception as e:
            return {
                'error': f'Process check failed: {e}',
                'timestamp': datetime.datetime.now().isoformat()
            }
    
    def monitor_database_changes(self, conn, duration_minutes: int = 5) -> List[Dict[str, Any]]:
        """Monitor database changes over time"""
        self.logger.info(f"Monitoring database changes for {duration_minutes} minutes...")
        
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        monitoring_data = []
        check_count = 0
        
        while datetime.datetime.now() < end_time:
            check_count += 1
            self.logger.info(f"=== DATABASE CHECK {check_count} ===")
            
            fabric_state = self.get_fabric_sync_state_direct(conn)
            
            evidence_point = {
                'check_number': check_count,
                'timestamp': datetime.datetime.now().isoformat(),
                'fabric_state': fabric_state
            }
            
            monitoring_data.append(evidence_point)
            
            # Log key findings
            if 'fabrics' in fabric_state:
                self.logger.info(f"Sync-enabled fabrics: {len(fabric_state['fabrics'])}")
                
                for fabric in fabric_state['fabrics']:
                    last_sync = fabric.get('last_sync', 'Never')
                    interval = fabric.get('sync_interval', 'Unknown')
                    self.logger.info(f"  Fabric {fabric['id']} ({fabric.get('name', 'Unknown')}): "
                                   f"Last sync: {last_sync}, Interval: {interval}s")
            
            # Save incremental evidence
            evidence_file = self.evidence_dir / f"monitoring_data_{self.timestamp}.json"
            with open(evidence_file, 'w') as f:
                json.dump(monitoring_data, f, indent=2)
            
            if datetime.datetime.now() < end_time:
                time.sleep(30)  # Check every 30 seconds
        
        return monitoring_data
    
    def analyze_database_monitoring(self, monitoring_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze database monitoring data for sync evidence"""
        analysis = {
            'analysis_timestamp': datetime.datetime.now().isoformat(),
            'total_checks': len(monitoring_data),
            'sync_activity_detected': False,
            'fabric_analysis': {},
            'definitive_conclusion': 'NO_SYNC_ACTIVITY'
        }
        
        if not monitoring_data:
            return analysis
        
        # Analyze each fabric for sync changes
        fabric_ids = set()
        for data_point in monitoring_data:
            fabric_state = data_point.get('fabric_state', {})
            if 'fabrics' in fabric_state:
                for fabric in fabric_state['fabrics']:
                    fabric_ids.add(str(fabric['id']))
        
        for fabric_id in fabric_ids:
            sync_timestamps = []
            fabric_name = 'Unknown'
            
            for data_point in monitoring_data:
                fabric_state = data_point.get('fabric_state', {})
                if 'fabrics' in fabric_state:
                    for fabric in fabric_state['fabrics']:
                        if str(fabric['id']) == fabric_id:
                            if fabric.get('last_sync') and fabric['last_sync'] != 'Never':
                                sync_timestamps.append(fabric['last_sync'])
                            fabric_name = fabric.get('name', 'Unknown')
            
            unique_timestamps = list(set(sync_timestamps))
            sync_detected = len(unique_timestamps) > 1
            
            if sync_detected:
                analysis['sync_activity_detected'] = True
            
            analysis['fabric_analysis'][fabric_id] = {
                'fabric_name': fabric_name,
                'sync_detected': sync_detected,
                'unique_sync_timestamps': unique_timestamps,
                'total_observations': len(sync_timestamps)
            }
        
        if analysis['sync_activity_detected']:
            analysis['definitive_conclusion'] = 'SYNC_IS_WORKING'
        else:
            analysis['definitive_conclusion'] = 'SYNC_IS_NOT_WORKING'
        
        return analysis
    
    def run_simple_validation_test(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """Run comprehensive simple validation test"""
        self.logger.info("=== STARTING SIMPLE PRODUCTION VALIDATION ===")
        
        validation_results = {
            'validation_metadata': {
                'start_time': datetime.datetime.now().isoformat(),
                'duration_minutes': duration_minutes,
                'validator_type': 'simple_direct_db'
            }
        }
        
        # Check Docker containers
        validation_results['docker_check'] = self.check_docker_containers()
        
        # Check processes
        validation_results['process_check'] = self.check_processes()
        
        # Try database connection
        conn = self.try_database_connection()
        
        if conn is None:
            validation_results['database_error'] = 'Could not connect to database'
            validation_results['definitive_conclusion'] = 'DATABASE_UNAVAILABLE'
            
            # Save partial results
            results_file = self.evidence_dir / f"simple_validation_results_{self.timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump(validation_results, f, indent=2)
            
            return validation_results
        
        try:
            # Monitor database for changes
            monitoring_data = self.monitor_database_changes(conn, duration_minutes)
            validation_results['database_monitoring'] = monitoring_data
            
            # Analyze monitoring data
            analysis = self.analyze_database_monitoring(monitoring_data)
            validation_results['analysis'] = analysis
            
            validation_results['definitive_conclusion'] = analysis['definitive_conclusion']
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            validation_results['validation_error'] = str(e)
            validation_results['definitive_conclusion'] = 'VALIDATION_ERROR'
        
        finally:
            conn.close()
        
        validation_results['validation_metadata']['end_time'] = datetime.datetime.now().isoformat()
        
        # Save comprehensive results
        results_file = self.evidence_dir / f"simple_validation_results_{self.timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(validation_results, f, indent=2)
        
        self.logger.info(f"Simple validation completed. Results: {results_file}")
        
        return validation_results


if __name__ == '__main__':
    validator = SimpleProductionValidator()
    
    if len(sys.argv) > 1:
        duration = int(sys.argv[1]) if sys.argv[1].isdigit() else 5
    else:
        duration = 5
    
    print(f"Running simple production validation for {duration} minutes...")
    
    results = validator.run_simple_validation_test(duration_minutes=duration)
    
    print("\n" + "="*60)
    print("SIMPLE PRODUCTION VALIDATION RESULTS")
    print("="*60)
    
    print(f"Docker containers found: {results.get('docker_check', {}).get('total_containers', 0)}")
    print(f"NetBox containers: {len(results.get('docker_check', {}).get('netbox_containers', []))}")
    print(f"Relevant processes: {results.get('process_check', {}).get('relevant_process_count', 0)}")
    
    analysis = results.get('analysis', {})
    print(f"\nDatabase monitoring checks: {analysis.get('total_checks', 0)}")
    print(f"Sync activity detected: {analysis.get('sync_activity_detected', False)}")
    
    fabric_analysis = analysis.get('fabric_analysis', {})
    for fabric_id, fabric_info in fabric_analysis.items():
        print(f"  Fabric {fabric_id} ({fabric_info['fabric_name']}): "
              f"Sync detected: {fabric_info['sync_detected']}")
    
    conclusion = results.get('definitive_conclusion', 'UNKNOWN')
    print(f"\n🎯 DEFINITIVE CONCLUSION: {conclusion}")
    
    if conclusion == 'SYNC_IS_WORKING':
        print("✅ EVIDENCE: Periodic sync functionality is WORKING")
    elif conclusion == 'SYNC_IS_NOT_WORKING':
        print("❌ EVIDENCE: Periodic sync functionality is NOT working")
    else:
        print("⚠️  EVIDENCE: Could not determine sync status")
    
    print(f"\nFull results saved to: {validator.evidence_dir}")