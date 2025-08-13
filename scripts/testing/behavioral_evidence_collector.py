#!/usr/bin/env python3
"""
Behavioral Evidence Collector
Captures behavioral evidence of sync functionality through system monitoring

FRAUD PREVENTION: Multi-layer evidence collection from system behavior
"""

import os
import sys
import json
import time
import psutil
import logging
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
import queue

class BehavioralEvidenceCollector:
    """
    Collect behavioral evidence of sync functionality by monitoring:
    - Process creation/termination
    - Network connections (especially Kubernetes API)
    - File system changes
    - Memory usage patterns
    - CPU usage spikes during sync operations
    """
    
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.evidence_dir = Path(f"behavioral_evidence_{self.timestamp}")
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logging()
        self.monitoring_active = False
        self.evidence_queue = queue.Queue()
        
        # Baseline system state
        self.baseline_processes = set()
        self.baseline_connections = set()
        self.baseline_cpu_percent = 0.0
        self.baseline_memory_percent = 0.0
        
    def _setup_logging(self):
        """Setup behavioral monitoring logging"""
        log_file = self.evidence_dir / "behavioral_evidence.log"
        
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
        logger.info("=== BEHAVIORAL EVIDENCE COLLECTION STARTED ===")
        
        return logger
    
    def establish_baseline(self):
        """Establish baseline system state before monitoring"""
        self.logger.info("Establishing system baseline...")
        
        # Baseline processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if any(keyword in str(proc_info).lower() for keyword in 
                      ['python', 'django', 'netbox', 'hedgehog', 'rq', 'redis', 'sync']):
                    self.baseline_processes.add(f"{proc_info['pid']}:{proc_info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Baseline network connections
        try:
            for conn in psutil.net_connections():
                if conn.status == 'ESTABLISHED':
                    self.baseline_connections.add(f"{conn.laddr.ip}:{conn.laddr.port}->{conn.raddr.ip if conn.raddr else 'unknown'}:{conn.raddr.port if conn.raddr else 'unknown'}")
        except psutil.AccessDenied:
            self.logger.warning("Cannot access network connections (permission denied)")
        
        # Baseline system resources
        self.baseline_cpu_percent = psutil.cpu_percent(interval=1)
        self.baseline_memory_percent = psutil.virtual_memory().percent
        
        baseline_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'process_count': len(self.baseline_processes),
            'connection_count': len(self.baseline_connections),
            'cpu_percent': self.baseline_cpu_percent,
            'memory_percent': self.baseline_memory_percent,
            'processes': list(self.baseline_processes)[:50],  # Limit output
            'connections': list(self.baseline_connections)[:50]
        }
        
        with open(self.evidence_dir / "system_baseline.json", 'w') as f:
            json.dump(baseline_data, f, indent=2)
        
        self.logger.info(f"Baseline established: {len(self.baseline_processes)} processes, "
                        f"{len(self.baseline_connections)} connections")
        
        return baseline_data
    
    def monitor_process_activity(self, duration_seconds: int = 300):
        """Monitor for new processes and process changes"""
        self.logger.info(f"Monitoring process activity for {duration_seconds} seconds...")
        
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_seconds)
        
        process_events = []
        last_process_set = self.baseline_processes.copy()
        
        while datetime.datetime.now() < end_time and self.monitoring_active:
            current_processes = set()
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    # Focus on potentially sync-related processes
                    if any(keyword in str(proc_info).lower() for keyword in 
                          ['python', 'django', 'netbox', 'hedgehog', 'rq', 'redis', 'sync', 'kubectl', 'kubernetes']):
                        
                        proc_key = f"{proc_info['pid']}:{proc_info['name']}"
                        current_processes.add(proc_key)
                        
                        # Check for new processes
                        if proc_key not in last_process_set:
                            event = {
                                'timestamp': datetime.datetime.now().isoformat(),
                                'event_type': 'process_started',
                                'process_info': proc_info
                            }
                            process_events.append(event)
                            self.logger.info(f"New process detected: {proc_info['name']} (PID: {proc_info['pid']})")
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Check for terminated processes
            for proc_key in last_process_set - current_processes:
                if proc_key in self.baseline_processes:  # Only report if it was in our baseline
                    event = {
                        'timestamp': datetime.datetime.now().isoformat(),
                        'event_type': 'process_terminated',
                        'process_key': proc_key
                    }
                    process_events.append(event)
                    self.logger.info(f"Process terminated: {proc_key}")
            
            last_process_set = current_processes
            time.sleep(5)  # Check every 5 seconds
        
        return process_events
    
    def monitor_network_activity(self, duration_seconds: int = 300):
        """Monitor network connections for Kubernetes API calls"""
        self.logger.info(f"Monitoring network activity for {duration_seconds} seconds...")
        
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_seconds)
        
        network_events = []
        last_connections = self.baseline_connections.copy()
        
        while datetime.datetime.now() < end_time and self.monitoring_active:
            try:
                current_connections = set()
                
                for conn in psutil.net_connections():
                    if conn.status == 'ESTABLISHED' and conn.raddr:
                        conn_key = f"{conn.laddr.ip}:{conn.laddr.port}->{conn.raddr.ip}:{conn.raddr.port}"
                        current_connections.add(conn_key)
                        
                        # Look for potentially Kubernetes-related connections
                        if (conn.raddr.port in [443, 6443, 8080, 8443] or  # Common k8s ports
                            '10.' in conn.raddr.ip or                        # Common k8s network
                            '192.168.' in conn.raddr.ip):                    # Common k8s network
                            
                            if conn_key not in last_connections:
                                event = {
                                    'timestamp': datetime.datetime.now().isoformat(),
                                    'event_type': 'new_connection',
                                    'connection': conn_key,
                                    'local_port': conn.laddr.port,
                                    'remote_port': conn.raddr.port,
                                    'potentially_k8s': True
                                }
                                network_events.append(event)
                                self.logger.info(f"New connection (potential K8s): {conn_key}")
                
                # Check for closed connections
                for conn_key in last_connections - current_connections:
                    if any(port in conn_key for port in [':443->', ':6443->', ':8080->', ':8443->']):
                        event = {
                            'timestamp': datetime.datetime.now().isoformat(),
                            'event_type': 'connection_closed',
                            'connection': conn_key,
                            'potentially_k8s': True
                        }
                        network_events.append(event)
                        self.logger.info(f"Connection closed (potential K8s): {conn_key}")
                
                last_connections = current_connections
                
            except psutil.AccessDenied:
                self.logger.debug("Cannot access network connections")
            
            time.sleep(10)  # Check every 10 seconds
        
        return network_events
    
    def monitor_system_resources(self, duration_seconds: int = 300):
        """Monitor CPU and memory for sync operation spikes"""
        self.logger.info(f"Monitoring system resources for {duration_seconds} seconds...")
        
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_seconds)
        
        resource_samples = []
        
        while datetime.datetime.now() < end_time and self.monitoring_active:
            sample = {
                'timestamp': datetime.datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_io': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
                'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}
            }
            
            # Detect significant changes from baseline
            cpu_change = abs(sample['cpu_percent'] - self.baseline_cpu_percent)
            memory_change = abs(sample['memory_percent'] - self.baseline_memory_percent)
            
            if cpu_change > 10 or memory_change > 5:  # Significant change thresholds
                sample['significant_change'] = True
                self.logger.info(f"Resource spike detected: CPU={sample['cpu_percent']:.1f}% (+{cpu_change:.1f}), "
                               f"Memory={sample['memory_percent']:.1f}% (+{memory_change:.1f})")
            
            resource_samples.append(sample)
            time.sleep(5)  # Sample every 5 seconds
        
        return resource_samples
    
    def monitor_file_system_changes(self, paths_to_watch: List[str], duration_seconds: int = 300):
        """Monitor file system changes in key directories"""
        self.logger.info(f"Monitoring file system changes for {duration_seconds} seconds...")
        
        # Take initial snapshots of watched directories
        initial_snapshots = {}
        for path in paths_to_watch:
            if os.path.exists(path):
                try:
                    files = {}
                    for root, dirs, filenames in os.walk(path):
                        for filename in filenames:
                            filepath = os.path.join(root, filename)
                            if os.path.exists(filepath):
                                stat = os.stat(filepath)
                                files[filepath] = {
                                    'size': stat.st_size,
                                    'mtime': stat.st_mtime
                                }
                    initial_snapshots[path] = files
                except Exception as e:
                    self.logger.debug(f"Cannot snapshot {path}: {e}")
        
        time.sleep(duration_seconds)
        
        # Take final snapshots and compare
        fs_changes = []
        for path in paths_to_watch:
            if path in initial_snapshots:
                try:
                    current_files = {}
                    for root, dirs, filenames in os.walk(path):
                        for filename in filenames:
                            filepath = os.path.join(root, filename)
                            if os.path.exists(filepath):
                                stat = os.stat(filepath)
                                current_files[filepath] = {
                                    'size': stat.st_size,
                                    'mtime': stat.st_mtime
                                }
                    
                    # Compare snapshots
                    initial = initial_snapshots[path]
                    
                    # New files
                    for filepath in current_files:
                        if filepath not in initial:
                            fs_changes.append({
                                'timestamp': datetime.datetime.now().isoformat(),
                                'change_type': 'file_created',
                                'path': filepath,
                                'size': current_files[filepath]['size']
                            })
                    
                    # Modified files
                    for filepath in current_files:
                        if filepath in initial:
                            if (current_files[filepath]['mtime'] != initial[filepath]['mtime'] or
                                current_files[filepath]['size'] != initial[filepath]['size']):
                                fs_changes.append({
                                    'timestamp': datetime.datetime.now().isoformat(),
                                    'change_type': 'file_modified',
                                    'path': filepath,
                                    'old_size': initial[filepath]['size'],
                                    'new_size': current_files[filepath]['size']
                                })
                    
                    # Deleted files
                    for filepath in initial:
                        if filepath not in current_files:
                            fs_changes.append({
                                'timestamp': datetime.datetime.now().isoformat(),
                                'change_type': 'file_deleted',
                                'path': filepath
                            })
                
                except Exception as e:
                    self.logger.debug(f"Cannot compare snapshots for {path}: {e}")
        
        if fs_changes:
            self.logger.info(f"File system changes detected: {len(fs_changes)} changes")
        
        return fs_changes
    
    def start_behavioral_monitoring(self, duration_minutes: int = 5):
        """Start comprehensive behavioral monitoring"""
        self.logger.info(f"Starting comprehensive behavioral monitoring for {duration_minutes} minutes")
        
        duration_seconds = duration_minutes * 60
        self.monitoring_active = True
        
        # Establish baseline
        baseline = self.establish_baseline()
        
        # Paths to monitor for changes
        watch_paths = [
            '/opt/netbox/logs',
            '/tmp',
            '/var/log'
        ]
        
        # Start monitoring threads
        threads = []
        results = {}
        
        # Process monitoring thread
        def process_monitor():
            results['process_events'] = self.monitor_process_activity(duration_seconds)
        
        # Network monitoring thread
        def network_monitor():
            results['network_events'] = self.monitor_network_activity(duration_seconds)
        
        # Resource monitoring thread
        def resource_monitor():
            results['resource_samples'] = self.monitor_system_resources(duration_seconds)
        
        # File system monitoring thread
        def filesystem_monitor():
            results['filesystem_changes'] = self.monitor_file_system_changes(watch_paths, duration_seconds)
        
        # Start all monitoring threads
        monitors = [
            threading.Thread(target=process_monitor, name="ProcessMonitor"),
            threading.Thread(target=network_monitor, name="NetworkMonitor"),
            threading.Thread(target=resource_monitor, name="ResourceMonitor"),
            threading.Thread(target=filesystem_monitor, name="FilesystemMonitor")
        ]
        
        for thread in monitors:
            thread.start()
            threads.append(thread)
        
        # Wait for all monitors to complete
        for thread in threads:
            thread.join()
        
        self.monitoring_active = False
        
        # Compile comprehensive results
        comprehensive_results = {
            'monitoring_metadata': {
                'start_time': datetime.datetime.now().isoformat(),
                'duration_minutes': duration_minutes,
                'baseline': baseline
            },
            'behavioral_evidence': results
        }
        
        # Save results
        results_file = self.evidence_dir / "comprehensive_behavioral_evidence.json"
        with open(results_file, 'w') as f:
            json.dump(comprehensive_results, f, indent=2)
        
        self.logger.info(f"Behavioral monitoring completed. Results saved to: {results_file}")
        
        return comprehensive_results
    
    def analyze_behavioral_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze behavioral evidence for sync activity indicators"""
        analysis = {
            'analysis_timestamp': datetime.datetime.now().isoformat(),
            'sync_activity_indicators': [],
            'confidence_level': 'none',
            'evidence_summary': {}
        }
        
        behavioral_data = evidence.get('behavioral_evidence', {})
        
        # Analyze process events
        process_events = behavioral_data.get('process_events', [])
        sync_related_processes = [
            event for event in process_events
            if any(keyword in str(event).lower() for keyword in ['sync', 'hedgehog', 'rq', 'django'])
        ]
        
        if sync_related_processes:
            analysis['sync_activity_indicators'].append(
                f"Process activity: {len(sync_related_processes)} sync-related process events"
            )
            analysis['confidence_level'] = 'low'
        
        # Analyze network events
        network_events = behavioral_data.get('network_events', [])
        k8s_connections = [
            event for event in network_events
            if event.get('potentially_k8s', False)
        ]
        
        if k8s_connections:
            analysis['sync_activity_indicators'].append(
                f"Network activity: {len(k8s_connections)} potential Kubernetes API connections"
            )
            if analysis['confidence_level'] == 'none':
                analysis['confidence_level'] = 'low'
            elif analysis['confidence_level'] == 'low':
                analysis['confidence_level'] = 'medium'
        
        # Analyze resource spikes
        resource_samples = behavioral_data.get('resource_samples', [])
        resource_spikes = [
            sample for sample in resource_samples
            if sample.get('significant_change', False)
        ]
        
        if resource_spikes:
            analysis['sync_activity_indicators'].append(
                f"Resource spikes: {len(resource_spikes)} significant CPU/memory changes"
            )
            if analysis['confidence_level'] in ['none', 'low']:
                analysis['confidence_level'] = 'medium'
        
        # Analyze file system changes
        fs_changes = behavioral_data.get('filesystem_changes', [])
        if fs_changes:
            analysis['sync_activity_indicators'].append(
                f"File system activity: {len(fs_changes)} file changes detected"
            )
        
        # Generate summary
        analysis['evidence_summary'] = {
            'total_process_events': len(process_events),
            'sync_related_process_events': len(sync_related_processes),
            'total_network_events': len(network_events),
            'k8s_related_network_events': len(k8s_connections),
            'resource_spike_count': len(resource_spikes),
            'filesystem_change_count': len(fs_changes)
        }
        
        return analysis


if __name__ == '__main__':
    collector = BehavioralEvidenceCollector()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'monitor':
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            evidence = collector.start_behavioral_monitoring(duration_minutes=duration)
            analysis = collector.analyze_behavioral_evidence(evidence)
            
            print("\n=== BEHAVIORAL EVIDENCE ANALYSIS ===")
            print(json.dumps(analysis, indent=2))
        elif sys.argv[1] == 'baseline':
            baseline = collector.establish_baseline()
            print("\n=== SYSTEM BASELINE ===")
            print(json.dumps(baseline, indent=2))
    else:
        print("Behavioral Evidence Collector")
        print("Usage:")
        print("  python behavioral_evidence_collector.py baseline         # Establish system baseline")
        print("  python behavioral_evidence_collector.py monitor [min]    # Monitor for N minutes (default 5)")