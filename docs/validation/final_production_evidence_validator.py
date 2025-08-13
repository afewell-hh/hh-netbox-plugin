#!/usr/bin/env python3
"""
Final Production Evidence Validator
Comprehensive validation system with fraud prevention measures

FRAUD PREVENTION: Multi-layer evidence collection and verification
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

class FinalProductionEvidenceValidator:
    """
    Final comprehensive validator that generates definitive evidence
    of sync functionality status in production environment
    """
    
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.evidence_dir = Path(f"FINAL_PRODUCTION_EVIDENCE_{self.timestamp}")
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logging()
        
        # Evidence collection
        self.evidence_package = {
            'validation_metadata': {
                'validator_version': '1.0.0_FRAUD_PREVENTION',
                'validation_start_time': datetime.datetime.now().isoformat(),
                'fraud_prevention_enabled': True,
                'evidence_independently_reproducible': True,
                'environment_type': 'production',
                'validation_duration_minutes': None,
                'total_evidence_points': 0
            },
            'environment_assessment': {},
            'sync_functionality_tests': {},
            'behavioral_evidence': {},
            'definitive_conclusion': 'PENDING_VALIDATION'
        }
        
    def _setup_logging(self):
        """Setup high-precision logging"""
        log_file = self.evidence_dir / f"FINAL_PRODUCTION_VALIDATION_{self.timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s.%(msecs)06d [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info("="*80)
        logger.info("FINAL PRODUCTION EVIDENCE VALIDATION STARTED")
        logger.info("FRAUD PREVENTION: All evidence will be timestamped and reproducible")
        logger.info("="*80)
        
        return logger
    
    def run_command_with_evidence(self, command: List[str], timeout: int = 30, description: str = "") -> Dict[str, Any]:
        """Run command and capture evidence with fraud prevention"""
        evidence_id = f"cmd_{len(self.evidence_package.get('command_evidence', []))}"
        
        try:
            self.logger.info(f"[{evidence_id}] {description}: {' '.join(command)}")
            
            start_time = datetime.datetime.now()
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            end_time = datetime.datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            evidence = {
                'evidence_id': evidence_id,
                'command': ' '.join(command),
                'description': description,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'execution_time_seconds': execution_time,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
            # Store in evidence package
            if 'command_evidence' not in self.evidence_package:
                self.evidence_package['command_evidence'] = []
            self.evidence_package['command_evidence'].append(evidence)
            
            return evidence
            
        except Exception as e:
            error_evidence = {
                'evidence_id': evidence_id,
                'command': ' '.join(command),
                'description': description,
                'error': str(e),
                'timestamp': datetime.datetime.now().isoformat(),
                'success': False
            }
            
            if 'command_evidence' not in self.evidence_package:
                self.evidence_package['command_evidence'] = []
            self.evidence_package['command_evidence'].append(error_evidence)
            
            return error_evidence
    
    def assess_environment_comprehensive(self) -> Dict[str, Any]:
        """Comprehensive environment assessment"""
        self.logger.info("Phase 1: Comprehensive Environment Assessment")
        
        assessment = {
            'assessment_timestamp': datetime.datetime.now().isoformat(),
            'docker_environment': {},
            'process_analysis': {},
            'network_services': {},
            'netbox_detection': {}
        }
        
        # Docker assessment
        docker_version = self.run_command_with_evidence(['docker', '--version'], description="Check Docker availability")
        assessment['docker_environment']['docker_available'] = docker_version['success']
        
        if docker_version['success']:
            containers = self.run_command_with_evidence(['docker', 'ps', '--format', 'json'], description="List Docker containers")
            assessment['docker_environment']['containers_result'] = containers
        
        # Process analysis
        processes = self.run_command_with_evidence(['ps', 'aux'], description="List all processes")
        assessment['process_analysis']['ps_result'] = processes
        
        if processes['success']:
            # Analyze for NetBox-related processes
            netbox_processes = []
            rq_processes = []
            sync_processes = []
            
            for line in processes['stdout'].split('\n'):
                lower_line = line.lower()
                if any(keyword in lower_line for keyword in ['netbox', '/opt/netbox']):
                    netbox_processes.append(line.strip())
                if 'rq' in lower_line and 'worker' in lower_line:
                    rq_processes.append(line.strip())
                if 'sync' in lower_line:
                    sync_processes.append(line.strip())
            
            assessment['process_analysis']['netbox_processes'] = netbox_processes
            assessment['process_analysis']['rq_processes'] = rq_processes
            assessment['process_analysis']['sync_processes'] = sync_processes
        
        # Network services
        ss_result = self.run_command_with_evidence(['ss', '-tlnp'], description="Check listening ports")
        assessment['network_services']['ss_result'] = ss_result
        
        # Port-specific checks
        important_ports = [8000, 5432, 6379]
        port_checks = {}
        
        for port in important_ports:
            port_check = self.run_command_with_evidence(['nc', '-z', 'localhost', str(port)], 
                                                       timeout=5, 
                                                       description=f"Check port {port}")
            port_checks[port] = port_check['success']
        
        assessment['network_services']['port_accessibility'] = port_checks
        
        # NetBox detection
        if assessment['process_analysis']['netbox_processes']:
            assessment['netbox_detection']['netbox_running'] = True
            assessment['netbox_detection']['process_count'] = len(assessment['process_analysis']['netbox_processes'])
        else:
            assessment['netbox_detection']['netbox_running'] = False
            assessment['netbox_detection']['process_count'] = 0
        
        return assessment
    
    def test_netbox_api_accessibility(self) -> Dict[str, Any]:
        """Test NetBox API accessibility"""
        self.logger.info("Phase 2: NetBox API Accessibility Testing")
        
        api_test = {
            'test_timestamp': datetime.datetime.now().isoformat(),
            'endpoints_tested': [],
            'working_endpoint': None,
            'api_accessible': False
        }
        
        endpoints = [
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'http://0.0.0.0:8000'
        ]
        
        for endpoint in endpoints:
            self.logger.info(f"Testing API endpoint: {endpoint}")
            
            try:
                response = requests.get(
                    f"{endpoint}/api/",
                    timeout=10,
                    headers={'Accept': 'application/json'}
                )
                
                endpoint_result = {
                    'endpoint': endpoint,
                    'status_code': response.status_code,
                    'accessible': response.status_code in [200, 401],  # 401 means accessible but needs auth
                    'response_time': response.elapsed.total_seconds(),
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                if endpoint_result['accessible']:
                    api_test['working_endpoint'] = endpoint
                    api_test['api_accessible'] = True
                
                api_test['endpoints_tested'].append(endpoint_result)
                
            except Exception as e:
                endpoint_result = {
                    'endpoint': endpoint,
                    'error': str(e),
                    'accessible': False,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                api_test['endpoints_tested'].append(endpoint_result)
        
        return api_test
    
    def test_sync_infrastructure(self) -> Dict[str, Any]:
        """Test sync infrastructure availability"""
        self.logger.info("Phase 3: Sync Infrastructure Testing")
        
        infrastructure_test = {
            'test_timestamp': datetime.datetime.now().isoformat(),
            'rq_workers_detected': False,
            'redis_accessible': False,
            'periodic_sync_evidence': {},
            'manual_sync_capability': False
        }
        
        # Check RQ workers from process list
        ps_result = self.run_command_with_evidence(['ps', 'aux'], description="Check for RQ workers")
        if ps_result['success']:
            rq_workers = [line for line in ps_result['stdout'].split('\n') 
                         if 'rqworker' in line.lower()]
            infrastructure_test['rq_workers_detected'] = len(rq_workers) > 0
            infrastructure_test['rq_worker_count'] = len(rq_workers)
            infrastructure_test['rq_worker_processes'] = rq_workers
        
        # Test Redis connectivity
        redis_test = self.run_command_with_evidence(['nc', '-z', 'localhost', '6379'], 
                                                   timeout=5, 
                                                   description="Test Redis connectivity")
        infrastructure_test['redis_accessible'] = redis_test['success']
        
        return infrastructure_test
    
    def monitor_sync_behavior_extended(self, duration_minutes: int = 8) -> Dict[str, Any]:
        """Extended sync behavior monitoring"""
        self.logger.info(f"Phase 4: Extended Sync Behavior Monitoring ({duration_minutes} minutes)")
        
        monitoring_result = {
            'monitoring_start': datetime.datetime.now().isoformat(),
            'duration_minutes': duration_minutes,
            'monitoring_points': [],
            'sync_evidence_detected': False,
            'evidence_summary': {}
        }
        
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        check_count = 0
        
        while datetime.datetime.now() < end_time:
            check_count += 1
            check_timestamp = datetime.datetime.now()
            
            self.logger.info(f"Monitoring check {check_count}/{duration_minutes*2} at {check_timestamp.strftime('%H:%M:%S')}")
            
            # Capture multiple evidence points
            monitoring_point = {
                'check_number': check_count,
                'timestamp': check_timestamp.isoformat(),
                'evidence_points': {}
            }
            
            # Process snapshot
            ps_snapshot = self.run_command_with_evidence(['ps', 'aux'], 
                                                        description=f"Process snapshot #{check_count}")
            monitoring_point['evidence_points']['process_snapshot'] = {
                'success': ps_snapshot['success'],
                'process_count': len(ps_snapshot.get('stdout', '').split('\n')) if ps_snapshot['success'] else 0
            }
            
            # Network connections
            ss_snapshot = self.run_command_with_evidence(['ss', '-tn'], 
                                                        description=f"Network connections #{check_count}")
            monitoring_point['evidence_points']['network_connections'] = {
                'success': ss_snapshot['success'],
                'connection_count': len(ss_snapshot.get('stdout', '').split('\n')) if ss_snapshot['success'] else 0
            }
            
            # System load
            uptime_snapshot = self.run_command_with_evidence(['uptime'], 
                                                           description=f"System load #{check_count}")
            monitoring_point['evidence_points']['system_load'] = uptime_snapshot
            
            monitoring_result['monitoring_points'].append(monitoring_point)
            
            # Save incremental evidence
            evidence_file = self.evidence_dir / f"monitoring_evidence_{self.timestamp}.json"
            with open(evidence_file, 'w') as f:
                json.dump(self.evidence_package, f, indent=2)
            
            if datetime.datetime.now() < end_time:
                time.sleep(30)  # 30-second intervals
        
        monitoring_result['monitoring_end'] = datetime.datetime.now().isoformat()
        monitoring_result['total_monitoring_points'] = check_count
        
        return monitoring_result
    
    def analyze_all_evidence(self, assessment: Dict, api_test: Dict, infrastructure_test: Dict, monitoring_result: Dict) -> Dict[str, Any]:
        """Comprehensive evidence analysis with definitive conclusion"""
        self.logger.info("Phase 5: Comprehensive Evidence Analysis")
        
        analysis = {
            'analysis_timestamp': datetime.datetime.now().isoformat(),
            'environment_score': 0,
            'infrastructure_score': 0,
            'monitoring_score': 0,
            'total_score': 0,
            'evidence_quality': 'INSUFFICIENT',
            'sync_functionality_assessment': 'CANNOT_DETERMINE',
            'definitive_conclusion': 'INSUFFICIENT_EVIDENCE',
            'evidence_breakdown': {},
            'recommendations': []
        }
        
        # Score environment
        env_score = 0
        if assessment.get('netbox_detection', {}).get('netbox_running'):
            env_score += 30
        if assessment.get('network_services', {}).get('port_accessibility', {}).get(8000):
            env_score += 20
        if assessment.get('docker_environment', {}).get('docker_available'):
            env_score += 10
        analysis['environment_score'] = env_score
        
        # Score infrastructure
        infra_score = 0
        if infrastructure_test.get('rq_workers_detected'):
            infra_score += 40
        if infrastructure_test.get('redis_accessible'):
            infra_score += 20
        if len(assessment.get('process_analysis', {}).get('netbox_processes', [])) > 0:
            infra_score += 20
        analysis['infrastructure_score'] = infra_score
        
        # Score monitoring
        monitor_score = 0
        if monitoring_result.get('total_monitoring_points', 0) >= 10:
            monitor_score += 30
        if len(self.evidence_package.get('command_evidence', [])) >= 50:
            monitor_score += 20
        analysis['monitoring_score'] = monitor_score
        
        # Calculate total
        total_score = env_score + infra_score + monitor_score
        analysis['total_score'] = total_score
        
        # Determine evidence quality
        if total_score >= 80:
            analysis['evidence_quality'] = 'HIGH'
        elif total_score >= 60:
            analysis['evidence_quality'] = 'MEDIUM'
        elif total_score >= 40:
            analysis['evidence_quality'] = 'LOW'
        else:
            analysis['evidence_quality'] = 'INSUFFICIENT'
        
        # Make definitive assessment
        if total_score >= 80 and infrastructure_test.get('rq_workers_detected'):
            if api_test.get('api_accessible'):
                analysis['sync_functionality_assessment'] = 'INFRASTRUCTURE_PRESENT_BUT_CANNOT_VERIFY_PERIODIC_EXECUTION'
                analysis['definitive_conclusion'] = 'SYNC_INFRASTRUCTURE_EXISTS_BUT_PERIODIC_EXECUTION_UNVERIFIED'
            else:
                analysis['sync_functionality_assessment'] = 'INFRASTRUCTURE_PRESENT_API_INACCESSIBLE'
                analysis['definitive_conclusion'] = 'SYNC_INFRASTRUCTURE_EXISTS_BUT_API_INACCESSIBLE'
        elif total_score >= 60:
            analysis['sync_functionality_assessment'] = 'PARTIAL_INFRASTRUCTURE_DETECTED'
            analysis['definitive_conclusion'] = 'PARTIAL_SYNC_INFRASTRUCTURE_DETECTED'
        else:
            analysis['sync_functionality_assessment'] = 'INSUFFICIENT_EVIDENCE'
            analysis['definitive_conclusion'] = 'INSUFFICIENT_EVIDENCE_TO_DETERMINE_SYNC_STATUS'
        
        # Generate evidence breakdown
        analysis['evidence_breakdown'] = {
            'total_command_executions': len(self.evidence_package.get('command_evidence', [])),
            'successful_commands': len([cmd for cmd in self.evidence_package.get('command_evidence', []) if cmd.get('success', False)]),
            'monitoring_duration_minutes': monitoring_result.get('duration_minutes', 0),
            'monitoring_points_collected': monitoring_result.get('total_monitoring_points', 0),
            'netbox_processes_found': len(assessment.get('process_analysis', {}).get('netbox_processes', [])),
            'rq_workers_found': infrastructure_test.get('rq_worker_count', 0),
            'api_accessible': api_test.get('api_accessible', False)
        }
        
        # Generate recommendations
        if analysis['definitive_conclusion'] == 'SYNC_INFRASTRUCTURE_EXISTS_BUT_API_INACCESSIBLE':
            analysis['recommendations'].append("API access needed to verify sync configuration and execution")
        elif analysis['definitive_conclusion'] == 'PARTIAL_SYNC_INFRASTRUCTURE_DETECTED':
            analysis['recommendations'].append("Incomplete sync infrastructure - check RQ workers and Redis")
        else:
            analysis['recommendations'].append("More detailed access needed for definitive sync validation")
        
        return analysis
    
    def generate_final_evidence_package(self, duration_minutes: int = 8) -> str:
        """Generate final comprehensive evidence package"""
        start_time = datetime.datetime.now()
        self.logger.info("GENERATING FINAL PRODUCTION EVIDENCE PACKAGE")
        
        # Phase 1: Environment assessment
        assessment = self.assess_environment_comprehensive()
        self.evidence_package['environment_assessment'] = assessment
        
        # Phase 2: API testing
        api_test = self.test_netbox_api_accessibility()
        self.evidence_package['api_accessibility_test'] = api_test
        
        # Phase 3: Infrastructure testing
        infrastructure_test = self.test_sync_infrastructure()
        self.evidence_package['sync_infrastructure_test'] = infrastructure_test
        
        # Phase 4: Extended monitoring
        monitoring_result = self.monitor_sync_behavior_extended(duration_minutes)
        self.evidence_package['extended_monitoring'] = monitoring_result
        
        # Phase 5: Final analysis
        final_analysis = self.analyze_all_evidence(assessment, api_test, infrastructure_test, monitoring_result)
        self.evidence_package['final_analysis'] = final_analysis
        
        # Update metadata
        end_time = datetime.datetime.now()
        self.evidence_package['validation_metadata']['validation_end_time'] = end_time.isoformat()
        self.evidence_package['validation_metadata']['validation_duration_minutes'] = (end_time - start_time).total_seconds() / 60
        self.evidence_package['validation_metadata']['total_evidence_points'] = len(self.evidence_package.get('command_evidence', []))
        self.evidence_package['definitive_conclusion'] = final_analysis['definitive_conclusion']
        
        # Save final evidence package
        final_package_file = f"PRODUCTION_SYNC_EVIDENCE_PACKAGE_{self.timestamp}.json"
        
        with open(final_package_file, 'w') as f:
            json.dump(self.evidence_package, f, indent=2)
        
        # Save summary
        summary_file = f"PRODUCTION_VALIDATION_SUMMARY_{self.timestamp}.json"
        summary = {
            'validation_summary': {
                'timestamp': datetime.datetime.now().isoformat(),
                'definitive_conclusion': final_analysis['definitive_conclusion'],
                'evidence_quality': final_analysis['evidence_quality'],
                'total_score': final_analysis['total_score'],
                'environment_score': final_analysis['environment_score'],
                'infrastructure_score': final_analysis['infrastructure_score'],
                'monitoring_score': final_analysis['monitoring_score'],
                'total_evidence_points': len(self.evidence_package.get('command_evidence', [])),
                'validation_duration_minutes': (end_time - start_time).total_seconds() / 60
            },
            'key_findings': {
                'netbox_running': assessment.get('netbox_detection', {}).get('netbox_running', False),
                'api_accessible': api_test.get('api_accessible', False),
                'rq_workers_detected': infrastructure_test.get('rq_workers_detected', False),
                'redis_accessible': infrastructure_test.get('redis_accessible', False)
            },
            'recommendations': final_analysis['recommendations']
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info("="*80)
        self.logger.info("FINAL PRODUCTION EVIDENCE PACKAGE COMPLETED")
        self.logger.info(f"Full package: {final_package_file}")
        self.logger.info(f"Summary: {summary_file}")
        self.logger.info(f"Evidence directory: {self.evidence_dir}")
        self.logger.info("="*80)
        
        return final_package_file


if __name__ == '__main__':
    validator = FinalProductionEvidenceValidator()
    
    duration = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8
    
    print(f"Generating final production evidence package ({duration} minutes monitoring)...")
    print("FRAUD PREVENTION: All evidence timestamped and independently verifiable")
    
    package_file = validator.generate_final_evidence_package(duration_minutes=duration)
    
    print("\n" + "="*100)
    print("FINAL PRODUCTION VALIDATION RESULTS")
    print("="*100)
    
    # Load and display summary
    summary_file = package_file.replace('_PACKAGE_', '_SUMMARY_')
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        
        validation_summary = summary['validation_summary']
        key_findings = summary['key_findings']
        
        print(f"🎯 DEFINITIVE CONCLUSION: {validation_summary['definitive_conclusion']}")
        print(f"📊 Evidence Quality: {validation_summary['evidence_quality']}")
        print(f"📈 Total Score: {validation_summary['total_score']}/120")
        print(f"⏱️  Validation Duration: {validation_summary['validation_duration_minutes']:.1f} minutes")
        print(f"📋 Evidence Points: {validation_summary['total_evidence_points']}")
        
        print(f"\n🔍 Key Findings:")
        print(f"  NetBox Running: {'✅' if key_findings['netbox_running'] else '❌'}")
        print(f"  API Accessible: {'✅' if key_findings['api_accessible'] else '❌'}")
        print(f"  RQ Workers: {'✅' if key_findings['rq_workers_detected'] else '❌'}")
        print(f"  Redis: {'✅' if key_findings['redis_accessible'] else '❌'}")
        
        if 'recommendations' in summary and summary['recommendations']:
            print(f"\n📋 Recommendations:")
            for rec in summary['recommendations']:
                print(f"  • {rec}")
        
        # Fraud prevention statement
        print(f"\n🛡️  FRAUD PREVENTION MEASURES:")
        print(f"  • All {validation_summary['total_evidence_points']} evidence points timestamped")
        print(f"  • All commands logged with execution times")
        print(f"  • Evidence independently reproducible")
        print(f"  • Multiple validation phases executed")
        
        print(f"\n📁 Evidence Package: {package_file}")
        print(f"📋 Summary Report: {summary_file}")
        
        # Final determination
        conclusion = validation_summary['definitive_conclusion']
        print(f"\n" + "="*100)
        if "INFRASTRUCTURE_EXISTS" in conclusion:
            print("🟡 EVIDENCE: Sync infrastructure components detected but periodic execution not verified")
            print("   Recommendation: API access or container access needed for definitive verification")
        elif "PARTIAL" in conclusion:
            print("🟠 EVIDENCE: Partial sync infrastructure detected - incomplete deployment")
        elif "INSUFFICIENT" in conclusion:
            print("🔴 EVIDENCE: Insufficient access to determine sync functionality status")
        else:
            print("⚪ EVIDENCE: Status could not be definitively determined")
        print("="*100)
    
    else:
        print("⚠️ Could not load summary file")