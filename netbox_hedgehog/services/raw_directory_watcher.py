"""
Raw Directory Watcher Service

Monitors the raw/ directory for new YAML files and automatically triggers ingestion.
Provides both event-driven and scheduled processing capabilities.
"""

import os
import logging
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.signals import request_finished

logger = logging.getLogger(__name__)


class RawDirectoryWatcher:
    """
    Service for monitoring raw/ directory and triggering automatic ingestion.
    
    Provides multiple monitoring modes:
    1. File system watching (inotify/polling)
    2. Scheduled scanning
    3. Manual trigger
    
    Integrates with GitOpsIngestionService for actual file processing.
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.raw_path = None
        self.is_watching = False
        self.watch_thread = None
        self.last_scan_time = None
        self.processing_lock = threading.Lock()
        
        # Configuration
        self.scan_interval = 30  # seconds
        self.debounce_delay = 2  # seconds to wait after file change
        self.max_file_age = 300  # seconds - ignore files older than this
        
        # Callbacks for integration
        self.on_files_detected = None
        self.on_processing_complete = None
        self.on_error = None
        
        # Statistics
        self.stats = {
            'files_detected': 0,
            'files_processed': 0,
            'processing_errors': 0,
            'last_processing_time': None,
            'watch_started_at': None
        }
    
    def start_watching(self, scan_interval: Optional[int] = None) -> Dict[str, Any]:
        """
        Start monitoring the raw directory for new files.
        
        Args:
            scan_interval: Override default scan interval in seconds
            
        Returns:
            Dict with start result
        """
        try:
            if self.is_watching:
                return {
                    'success': False,
                    'message': 'Watcher is already running'
                }
            
            # Initialize paths
            self._initialize_paths()
            
            if not self._validate_paths():
                return {
                    'success': False,
                    'error': 'Raw directory path not configured or does not exist'
                }
            
            # Set configuration
            if scan_interval:
                self.scan_interval = scan_interval
            
            # Start watch thread
            self.is_watching = True
            self.stats['watch_started_at'] = timezone.now()
            self.watch_thread = threading.Thread(
                target=self._watch_loop,
                name=f"RawWatcher-{self.fabric.name}",
                daemon=True
            )
            self.watch_thread.start()
            
            logger.info(f"Started raw directory watcher for fabric {self.fabric.name} (interval: {self.scan_interval}s)")
            return {
                'success': True,
                'message': f'Started watching {self.raw_path}',
                'scan_interval': self.scan_interval,
                'raw_path': str(self.raw_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to start raw directory watcher: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_watching(self) -> Dict[str, Any]:
        """
        Stop monitoring the raw directory.
        
        Returns:
            Dict with stop result
        """
        try:
            if not self.is_watching:
                return {
                    'success': False,
                    'message': 'Watcher is not running'
                }
            
            # Signal thread to stop
            self.is_watching = False
            
            # Wait for thread to finish
            if self.watch_thread and self.watch_thread.is_alive():
                self.watch_thread.join(timeout=10)
                if self.watch_thread.is_alive():
                    logger.warning(f"Watch thread for fabric {self.fabric.name} did not stop gracefully")
            
            logger.info(f"Stopped raw directory watcher for fabric {self.fabric.name}")
            return {
                'success': True,
                'message': 'Watcher stopped successfully',
                'statistics': self.get_statistics()
            }
            
        except Exception as e:
            logger.error(f"Failed to stop raw directory watcher: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def scan_once(self) -> Dict[str, Any]:
        """
        Perform a single scan of the raw directory.
        
        Returns:
            Dict with scan results
        """
        try:
            self._initialize_paths()
            
            if not self._validate_paths():
                return {
                    'success': False,
                    'error': 'Raw directory path not configured or does not exist'
                }
            
            # Find new files
            new_files = self._find_new_files()
            
            if not new_files:
                return {
                    'success': True,
                    'message': 'No new files found',
                    'files_found': 0
                }
            
            # Process files
            processing_result = self._process_detected_files(new_files)
            
            return {
                'success': True,
                'message': f'Scanned and processed {len(new_files)} files',
                'files_found': len(new_files),
                'files_processed': len(processing_result.get('files_processed', [])),
                'processing_result': processing_result
            }
            
        except Exception as e:
            logger.error(f"Failed to perform single scan: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _initialize_paths(self):
        """Initialize directory paths from fabric configuration."""
        if hasattr(self.fabric, 'raw_directory_path') and self.fabric.raw_directory_path:
            self.raw_path = Path(self.fabric.raw_directory_path)
        else:
            # Fallback path construction
            base_path = self._get_base_directory_path()
            self.raw_path = base_path / 'raw'
    
    def _get_base_directory_path(self) -> Path:
        """Get the base directory path for this fabric's GitOps structure."""
        # Use existing Git repository path if available
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            git_path = getattr(self.fabric.git_repository, 'local_path', None)
            if git_path:
                return Path(git_path) / 'fabrics' / self.fabric.name / 'gitops'
        
        # Fall back to legacy Git configuration
        if self.fabric.git_repository_url:
            repo_name = self.fabric.name.lower().replace(' ', '-').replace('_', '-')
            return Path(f"/tmp/hedgehog-repos/{repo_name}/fabrics/{self.fabric.name}/gitops")
        
        # Default fallback
        return Path(f"/var/lib/hedgehog/fabrics/{self.fabric.name}/gitops")
    
    def _validate_paths(self) -> bool:
        """Validate that required paths exist."""
        if not self.raw_path or not self.raw_path.exists():
            logger.error(f"Raw directory does not exist: {self.raw_path}")
            return False
        
        if not self.raw_path.is_dir():
            logger.error(f"Raw path is not a directory: {self.raw_path}")
            return False
        
        return True
    
    def _watch_loop(self):
        """Main watch loop running in separate thread."""
        logger.info(f"Watch loop started for fabric {self.fabric.name}")
        
        while self.is_watching:
            try:
                # Find new files
                new_files = self._find_new_files()
                
                if new_files:
                    logger.info(f"Detected {len(new_files)} new files in {self.raw_path}")
                    self.stats['files_detected'] += len(new_files)
                    
                    # Notify callback if registered
                    if self.on_files_detected:
                        self.on_files_detected(new_files)
                    
                    # Process files
                    processing_result = self._process_detected_files(new_files)
                    
                    # Update statistics
                    if processing_result.get('success'):
                        self.stats['files_processed'] += processing_result.get('files_processed_count', 0)
                        self.stats['last_processing_time'] = timezone.now()
                        
                        # Notify callback if registered
                        if self.on_processing_complete:
                            self.on_processing_complete(processing_result)
                    else:
                        self.stats['processing_errors'] += 1
                        
                        # Notify error callback if registered
                        if self.on_error:
                            self.on_error(processing_result.get('error'))
                
                # Update last scan time
                self.last_scan_time = timezone.now()
                
                # Sleep until next scan
                time.sleep(self.scan_interval)
                
            except Exception as e:
                logger.error(f"Error in watch loop for fabric {self.fabric.name}: {str(e)}")
                self.stats['processing_errors'] += 1
                
                if self.on_error:
                    self.on_error(str(e))
                
                # Sleep before retrying
                time.sleep(min(self.scan_interval, 60))
        
        logger.info(f"Watch loop stopped for fabric {self.fabric.name}")
    
    def _find_new_files(self) -> List[Path]:
        """Find new YAML files in the raw directory."""
        new_files = []
        current_time = time.time()
        
        try:
            # Look for YAML files
            for pattern in ['*.yaml', '*.yml']:
                for file_path in self.raw_path.glob(pattern):
                    if self._should_process_file(file_path, current_time):
                        new_files.append(file_path)
            
            # Sort by modification time (oldest first)
            new_files.sort(key=lambda x: x.stat().st_mtime)
            
        except Exception as e:
            logger.error(f"Error finding new files: {str(e)}")
        
        return new_files
    
    def _should_process_file(self, file_path: Path, current_time: float) -> bool:
        """Determine if a file should be processed."""
        try:
            # Check if file is too old
            file_mtime = file_path.stat().st_mtime
            if current_time - file_mtime > self.max_file_age:
                return False
            
            # Check if file was recently modified (debounce)
            if current_time - file_mtime < self.debounce_delay:
                return False
            
            # Check if file is readable and not empty
            if file_path.stat().st_size == 0:
                return False
            
            # Basic file accessibility check
            with open(file_path, 'r') as f:
                f.read(1)  # Try to read first character
            
            return True
            
        except Exception as e:
            logger.warning(f"Could not check file {file_path}: {str(e)}")
            return False
    
    def _process_detected_files(self, files: List[Path]) -> Dict[str, Any]:
        """Process detected files using GitOpsIngestionService."""
        # Prevent concurrent processing
        if not self.processing_lock.acquire(blocking=False):
            return {
                'success': False,
                'error': 'Processing already in progress'
            }
        
        try:
            from .gitops_ingestion_service import GitOpsIngestionService
            
            # Create ingestion service
            ingestion_service = GitOpsIngestionService(self.fabric)
            
            # Process each file
            processing_results = []
            for file_path in files:
                try:
                    result = ingestion_service.process_single_file(file_path)
                    processing_results.append({
                        'file': str(file_path),
                        'result': result
                    })
                    
                    if result.get('success'):
                        logger.info(f"Successfully processed {file_path}")
                    else:
                        logger.error(f"Failed to process {file_path}: {result.get('error')}")
                        
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")
                    processing_results.append({
                        'file': str(file_path),
                        'result': {'success': False, 'error': str(e)}
                    })
            
            # Summarize results
            successful_files = [r for r in processing_results if r['result'].get('success')]
            failed_files = [r for r in processing_results if not r['result'].get('success')]
            
            return {
                'success': len(failed_files) == 0,
                'files_processed': processing_results,
                'files_processed_count': len(successful_files),
                'successful_files': len(successful_files),
                'failed_files': len(failed_files),
                'processing_time': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error during file processing: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.processing_lock.release()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get watcher statistics."""
        return {
            'fabric_name': self.fabric.name,
            'is_watching': self.is_watching,
            'raw_path': str(self.raw_path) if self.raw_path else None,
            'scan_interval': self.scan_interval,
            'last_scan_time': self.last_scan_time,
            'statistics': self.stats.copy(),
            'thread_alive': self.watch_thread.is_alive() if self.watch_thread else False
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current watcher status."""
        status = self.get_statistics()
        
        # Add health checks
        status['healthy'] = True
        status['health_issues'] = []
        
        # Check if paths are valid
        if not self._validate_paths():
            status['healthy'] = False
            status['health_issues'].append('Raw directory path invalid or missing')
        
        # Check if thread is running when it should be
        if self.is_watching and (not self.watch_thread or not self.watch_thread.is_alive()):
            status['healthy'] = False
            status['health_issues'].append('Watch thread not running')
        
        # Check if scanning is too infrequent
        if self.last_scan_time:
            time_since_scan = timezone.now() - self.last_scan_time
            if time_since_scan > timedelta(seconds=self.scan_interval * 3):
                status['healthy'] = False
                status['health_issues'].append(f'No scan in {time_since_scan.total_seconds():.0f} seconds')
        
        return status
    
    def register_callbacks(self, 
                          on_files_detected: Optional[Callable] = None,
                          on_processing_complete: Optional[Callable] = None, 
                          on_error: Optional[Callable] = None):
        """Register callback functions for watcher events."""
        if on_files_detected:
            self.on_files_detected = on_files_detected
        if on_processing_complete:
            self.on_processing_complete = on_processing_complete
        if on_error:
            self.on_error = on_error


class RawDirectoryWatcherManager:
    """
    Manager class for handling multiple fabric watchers.
    Provides centralized control and monitoring of all raw directory watchers.
    """
    
    def __init__(self):
        self.watchers: Dict[int, RawDirectoryWatcher] = {}
        self.global_stats = {
            'total_watchers': 0,
            'active_watchers': 0,
            'total_files_processed': 0,
            'total_errors': 0
        }
    
    def start_watcher_for_fabric(self, fabric, scan_interval: Optional[int] = None) -> Dict[str, Any]:
        """Start a watcher for a specific fabric."""
        try:
            fabric_id = fabric.id
            
            # Stop existing watcher if running
            if fabric_id in self.watchers and self.watchers[fabric_id].is_watching:
                self.watchers[fabric_id].stop_watching()
            
            # Create and start new watcher
            watcher = RawDirectoryWatcher(fabric)
            result = watcher.start_watching(scan_interval)
            
            if result['success']:
                self.watchers[fabric_id] = watcher
                self.global_stats['total_watchers'] += 1
                self.global_stats['active_watchers'] = len([w for w in self.watchers.values() if w.is_watching])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to start watcher for fabric {fabric.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_watcher_for_fabric(self, fabric) -> Dict[str, Any]:
        """Stop the watcher for a specific fabric."""
        try:
            fabric_id = fabric.id
            
            if fabric_id not in self.watchers:
                return {
                    'success': False,
                    'message': f'No watcher running for fabric {fabric.name}'
                }
            
            result = self.watchers[fabric_id].stop_watching()
            
            if result['success']:
                del self.watchers[fabric_id]
                self.global_stats['active_watchers'] = len([w for w in self.watchers.values() if w.is_watching])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to stop watcher for fabric {fabric.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_all_watcher_status(self) -> Dict[str, Any]:
        """Get status of all watchers."""
        watcher_statuses = {}
        
        for fabric_id, watcher in self.watchers.items():
            watcher_statuses[fabric_id] = watcher.get_status()
        
        return {
            'global_stats': self.global_stats,
            'watchers': watcher_statuses,
            'summary': {
                'total_watchers': len(self.watchers),
                'healthy_watchers': len([s for s in watcher_statuses.values() if s['healthy']]),
                'unhealthy_watchers': len([s for s in watcher_statuses.values() if not s['healthy']])
            }
        }
    
    def stop_all_watchers(self) -> Dict[str, Any]:
        """Stop all watchers."""
        results = {}
        
        for fabric_id, watcher in list(self.watchers.items()):
            try:
                result = watcher.stop_watching()
                results[fabric_id] = result
                if result['success']:
                    del self.watchers[fabric_id]
            except Exception as e:
                results[fabric_id] = {'success': False, 'error': str(e)}
        
        self.global_stats['active_watchers'] = 0
        
        return {
            'success': True,
            'stopped_watchers': len(results),
            'results': results
        }


# Global manager instance
raw_directory_watcher_manager = RawDirectoryWatcherManager()