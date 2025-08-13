#!/usr/bin/env python3
"""
Periodic Sync Monitoring and Testing
Real-time monitoring of periodic sync job execution
"""

import asyncio
import json
import time
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PeriodicSyncMonitor:
    """Monitor and test periodic sync functionality"""
    
    def __init__(self):
        self.container_id = "b05eb5eff181"
        self.test_session_id = f"periodic_monitor_{int(time.time())}"
        self.monitoring_active = False
        self.job_executions = []
        self.scheduler_status = {}
    
    async def check_rq_scheduler_status(self) -> Dict[str, Any]:
        """Check RQ scheduler configuration and status"""
        start_time = time.time()
        
        try:
            # Check if RQ scheduler is configured
            scheduler_check = subprocess.run([
                'docker', 'exec', self.container_id,
                'python', 'manage.py', 'shell', '-c',
                '''
from django_rq import get_scheduler
from rq_scheduler import Scheduler
import redis

try:
    scheduler = get_scheduler('default')
    redis_conn = scheduler.connection
    
    # Check Redis connection
    redis_conn.ping()
    
    # Get scheduled jobs
    jobs = list(scheduler.get_jobs())  # Convert generator to list for len() operation
    
    result = {
        "scheduler_connected": True,
        "redis_connected": True,
        "scheduled_jobs_count": len(jobs),
        "job_details": []
    }
    
    for job in jobs:
        result["job_details"].append({
            "id": job.id,
            "func_name": str(job.func),
            "scheduled_time": str(job.scheduled_time) if hasattr(job, "scheduled_time") else "N/A",
            "repeat": getattr(job, "repeat", None)
        })
    
    print(f"SCHEDULER_STATUS: {result}")
    
except Exception as e:
    print(f"SCHEDULER_ERROR: {str(e)}")
                '''
            ], capture_output=True, text=True, timeout=15)
            
            output_lines = scheduler_check.stdout.strip().split('\n')
            status_line = None
            
            for line in output_lines:
                if line.startswith('SCHEDULER_STATUS:') or line.startswith('SCHEDULER_ERROR:'):
                    status_line = line
                    break
            
            if status_line and status_line.startswith('SCHEDULER_STATUS:'):
                status_data = eval(status_line.replace('SCHEDULER_STATUS: ', ''))
                result = {
                    "test_name": "RQ Scheduler Status Check",
                    "status": "PASS",
                    "duration": time.time() - start_time,
                    "details": status_data
                }
            else:
                result = {
                    "test_name": "RQ Scheduler Status Check", 
                    "status": "FAIL",
                    "duration": time.time() - start_time,
                    "error": status_line or "No scheduler status returned",
                    "details": {
                        "stdout": scheduler_check.stdout,
                        "stderr": scheduler_check.stderr
                    }
                }
            
            self.scheduler_status = result
            return result
            
        except Exception as e:
            return {
                "test_name": "RQ Scheduler Status Check",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def monitor_periodic_job_execution(self, duration_minutes: int = 3) -> Dict[str, Any]:
        """Monitor periodic job execution over specified duration"""
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        logger.info(f"🔄 Starting periodic sync monitoring for {duration_minutes} minutes...")
        
        executions_detected = []
        
        try:
            while time.time() < end_time:
                # Check RQ worker activity
                worker_check = subprocess.run([
                    'docker', 'exec', self.container_id,
                    'python', '-c',
                    '''
import redis
from rq import Queue, Worker
from django_rq import get_connection

try:
    conn = get_connection('default')
    queue = Queue('default', connection=conn)
    workers = Worker.all(connection=conn)
    
    result = {
        "queue_size": len(queue),
        "workers_count": len(workers),
        "workers_active": [w.name for w in workers if w.get_state() == 'busy'],
        "recent_jobs": []
    }
    
    # Get recent job info
    for job in list(queue.get_jobs())[:5]:  # Last 5 jobs (convert generator to list)
        result["recent_jobs"].append({
            "id": job.id,
            "func": str(job.func),
            "status": job.get_status(),
            "created_at": str(job.created_at) if job.created_at else None
        })
    
    print(f"WORKER_STATUS: {result}")
    
except Exception as e:
    print(f"WORKER_ERROR: {str(e)}")
                    '''
                ], capture_output=True, text=True, timeout=10)
                
                # Parse worker status
                output_lines = worker_check.stdout.strip().split('\n')
                for line in output_lines:
                    if line.startswith('WORKER_STATUS:'):
                        try:
                            worker_data = eval(line.replace('WORKER_STATUS: ', ''))
                            
                            # Check for job execution indicators
                            if worker_data.get('workers_active') or worker_data.get('queue_size', 0) > 0:
                                execution_event = {
                                    "timestamp": datetime.now().isoformat(),
                                    "worker_data": worker_data,
                                    "monitoring_duration": time.time() - start_time
                                }
                                executions_detected.append(execution_event)
                                logger.info(f"🎯 Job execution detected: {len(worker_data.get('workers_active', []))} active workers")
                        
                        except Exception as parse_error:
                            logger.warning(f"Failed to parse worker status: {parse_error}")
                
                await asyncio.sleep(10)  # Check every 10 seconds
            
            result = {
                "test_name": "Periodic Job Execution Monitor",
                "status": "PASS" if executions_detected else "FAIL",
                "duration": time.time() - start_time,
                "details": {
                    "monitoring_duration_minutes": duration_minutes,
                    "executions_detected": len(executions_detected),
                    "execution_events": executions_detected,
                    "expected_executions": duration_minutes,  # Assuming 60-second interval
                    "detection_rate": len(executions_detected) / duration_minutes if duration_minutes > 0 else 0
                }
            }
            
            if not executions_detected:
                result["error"] = f"No periodic job executions detected during {duration_minutes}-minute monitoring period"
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Periodic Job Execution Monitor",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def test_job_scheduling_configuration(self) -> Dict[str, Any]:
        """Test if periodic sync job is properly scheduled"""
        start_time = time.time()
        
        try:
            # Check Django management command for periodic sync setup
            management_check = subprocess.run([
                'docker', 'exec', self.container_id,
                'python', 'manage.py', 'shell', '-c',
                '''
from django.core.management import get_commands
from netbox_hedgehog.tasks.sync_tasks import schedule_periodic_sync
import importlib

# Check if periodic sync command exists
commands = get_commands()
has_periodic_command = any('periodic' in cmd and 'sync' in cmd for cmd in commands.keys())

# Check if sync tasks module exists
try:
    sync_tasks = importlib.import_module('netbox_hedgehog.tasks.sync_tasks')
    has_sync_tasks = hasattr(sync_tasks, 'schedule_periodic_sync')
    has_sync_func = hasattr(sync_tasks, 'periodic_fabric_sync')
except ImportError:
    has_sync_tasks = False
    has_sync_func = False

result = {
    "has_periodic_command": has_periodic_command,
    "has_sync_tasks_module": has_sync_tasks,
    "has_sync_function": has_sync_func,
    "available_commands": [cmd for cmd in commands.keys() if 'sync' in cmd.lower()]
}

print(f"SCHEDULING_CHECK: {result}")
                '''
            ], capture_output=True, text=True, timeout=15)
            
            output_lines = management_check.stdout.strip().split('\n')
            scheduling_data = None
            
            for line in output_lines:
                if line.startswith('SCHEDULING_CHECK:'):
                    scheduling_data = eval(line.replace('SCHEDULING_CHECK: ', ''))
                    break
            
            if scheduling_data:
                # Determine if configuration is complete
                config_complete = all([
                    scheduling_data.get('has_sync_tasks_module', False),
                    scheduling_data.get('has_sync_function', False)
                ])
                
                result = {
                    "test_name": "Job Scheduling Configuration",
                    "status": "PASS" if config_complete else "FAIL",
                    "duration": time.time() - start_time,
                    "details": scheduling_data
                }
                
                if not config_complete:
                    result["error"] = "Periodic sync scheduling configuration is incomplete"
            else:
                result = {
                    "test_name": "Job Scheduling Configuration",
                    "status": "FAIL",
                    "duration": time.time() - start_time,
                    "error": "Could not retrieve scheduling configuration",
                    "details": {
                        "stdout": management_check.stdout,
                        "stderr": management_check.stderr
                    }
                }
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Job Scheduling Configuration",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def run_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Run comprehensive periodic sync monitoring"""
        logger.info(f"⏱️  Starting comprehensive periodic sync monitoring - Session: {self.test_session_id}")
        
        # Run tests
        results = []
        
        # Check scheduler status
        scheduler_result = await self.check_rq_scheduler_status()
        results.append(scheduler_result)
        
        # Check scheduling configuration
        config_result = await self.test_job_scheduling_configuration()
        results.append(config_result)
        
        # Monitor job execution (shorter duration for testing)
        monitor_result = await self.monitor_periodic_job_execution(duration_minutes=2)
        results.append(monitor_result)
        
        # Generate summary
        summary = {
            "session_id": self.test_session_id,
            "timestamp": datetime.now().isoformat(),
            "test_type": "Periodic Sync Monitoring",
            "results": results,
            "summary": {
                "total_tests": len(results),
                "passed": len([r for r in results if r["status"] == "PASS"]),
                "failed": len([r for r in results if r["status"] == "FAIL"]),
                "errors": len([r for r in results if r["status"] == "ERROR"])
            },
            "recommendations": self.generate_recommendations(results)
        }
        
        # Save results
        results_file = f"periodic_sync_monitoring_{self.test_session_id}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📊 Periodic sync monitoring results saved to: {results_file}")
        
        # Log results
        for result in results:
            status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
            logger.info(f"{status_icon} {result['test_name']}: {result['status']}")
            
            if "error" in result:
                logger.error(f"   Error: {result['error']}")
        
        return summary
    
    def generate_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on monitoring results"""
        recommendations = []
        
        for result in results:
            if result["status"] == "FAIL":
                if "RQ Scheduler" in result["test_name"]:
                    recommendations.extend([
                        "Start RQ scheduler service: python manage.py rqscheduler",
                        "Verify Redis connection and configuration",
                        "Check django-rq settings in Django configuration"
                    ])
                
                if "Job Scheduling" in result["test_name"]:
                    recommendations.extend([
                        "Implement periodic sync scheduling in netbox_hedgehog.tasks.sync_tasks",
                        "Create Django management command for periodic sync setup",
                        "Verify task function imports and availability"
                    ])
                
                if "Execution Monitor" in result["test_name"]:
                    recommendations.extend([
                        "Check if periodic sync job is actually scheduled",
                        "Verify RQ worker is running and processing jobs",
                        "Review sync task implementation for errors"
                    ])
        
        if not recommendations:
            recommendations.append("Periodic sync monitoring shows all systems operational")
        
        return list(set(recommendations))  # Remove duplicates

async def main():
    """Main monitoring execution"""
    monitor = PeriodicSyncMonitor()
    
    try:
        summary = await monitor.run_comprehensive_monitoring()
        
        print("\n" + "="*70)
        print("⏱️  PERIODIC SYNC MONITORING RESULTS")
        print("="*70)
        print(f"📋 Session ID: {summary['session_id']}")
        print(f"✅ Passed: {summary['summary']['passed']}")
        print(f"❌ Failed: {summary['summary']['failed']}")
        print(f"⚠️  Errors: {summary['summary']['errors']}")
        
        if summary['recommendations']:
            print("\n🔧 RECOMMENDATIONS:")
            for i, rec in enumerate(summary['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        print("="*70)
        
        return summary
        
    except Exception as e:
        logger.error(f"Periodic sync monitoring failed: {e}")
        return {"error": str(e), "status": "MONITORING_ERROR"}

if __name__ == "__main__":
    asyncio.run(main())