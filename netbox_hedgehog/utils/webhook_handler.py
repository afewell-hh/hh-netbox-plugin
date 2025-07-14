"""
Webhook Handler for Git Repository Events.

This module provides secure webhook processing for GitHub and GitLab events
that trigger GitOps synchronization operations. It includes:
- Signature validation for GitHub webhooks
- Token validation for GitLab webhooks  
- Async webhook processing queue
- Integration with GitRepositoryMonitor
- Event filtering and routing

Author: Git Operations Agent
Date: July 9, 2025
"""

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from urllib.parse import urlparse

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from django.conf import settings

from .git_monitor import GitRepositoryMonitor
from ..models.fabric import HedgehogFabric

logger = logging.getLogger(__name__)


class WebhookSecurityError(Exception):
    """Exception raised for webhook security validation failures."""
    pass


class WebhookProcessingError(Exception):
    """Exception raised for webhook processing failures."""
    pass


class WebhookEventProcessor:
    """
    Processes Git webhook events and triggers appropriate GitOps operations.
    
    Supports GitHub and GitLab webhook events with security validation
    and async processing capabilities.
    """
    
    # GitHub event types that trigger sync
    GITHUB_SYNC_EVENTS = {
        'push',
        'pull_request',
        'release'
    }
    
    # GitLab event types that trigger sync
    GITLAB_SYNC_EVENTS = {
        'Push Hook',
        'Merge Request Hook',
        'Release Hook'
    }
    
    def __init__(self):
        """Initialize webhook event processor."""
        self.logger = logging.getLogger(f"{__name__}.WebhookEventProcessor")
        self._processing_queue = asyncio.Queue()
        self._processor_task = None
    
    async def start_processor(self):
        """Start the async webhook processor task."""
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_webhook_queue())
            self.logger.info("Webhook processor started")
    
    async def stop_processor(self):
        """Stop the async webhook processor task."""
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Webhook processor stopped")
    
    async def _process_webhook_queue(self):
        """Process webhooks from the async queue."""
        while True:
            try:
                webhook_data = await self._processing_queue.get()
                await self._process_single_webhook(webhook_data)
                self._processing_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing webhook from queue: {e}")
    
    async def queue_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Queue a webhook for async processing.
        
        Args:
            webhook_data: Webhook event data
            
        Returns:
            True if queued successfully
        """
        try:
            await self._processing_queue.put(webhook_data)
            self.logger.debug(f"Queued webhook for processing: {webhook_data.get('event_type', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to queue webhook: {e}")
            return False
    
    async def _process_single_webhook(self, webhook_data: Dict[str, Any]):
        """
        Process a single webhook event.
        
        Args:
            webhook_data: Webhook event data including fabric, event_type, and payload
        """
        try:
            fabric = webhook_data['fabric']
            event_type = webhook_data['event_type']
            payload = webhook_data['payload']
            provider = webhook_data['provider']
            
            self.logger.info(
                f"Processing {provider} webhook event '{event_type}' for fabric {fabric.name}"
            )
            
            # Check if event should trigger sync
            if not self._should_trigger_sync(event_type, provider, payload, fabric):
                self.logger.debug(f"Event {event_type} does not trigger sync for fabric {fabric.name}")
                return
            
            # Trigger Git sync
            async with GitRepositoryMonitor(fabric) as monitor:
                sync_result = await monitor.sync_to_database()
                
                if sync_result.success:
                    self.logger.info(
                        f"Webhook-triggered sync completed successfully for fabric {fabric.name}: "
                        f"{sync_result.message}"
                    )
                else:
                    self.logger.error(
                        f"Webhook-triggered sync failed for fabric {fabric.name}: "
                        f"{sync_result.message}"
                    )
                    if sync_result.errors:
                        for error in sync_result.errors:
                            self.logger.error(f"Sync error: {error}")
        
        except Exception as e:
            self.logger.error(f"Error processing webhook: {e}")
            raise WebhookProcessingError(f"Webhook processing failed: {e}")
    
    def _should_trigger_sync(
        self, 
        event_type: str, 
        provider: str, 
        payload: Dict[str, Any], 
        fabric: HedgehogFabric
    ) -> bool:
        """
        Determine if webhook event should trigger Git sync.
        
        Args:
            event_type: Type of webhook event
            provider: Git provider (github/gitlab)
            payload: Webhook payload data
            fabric: Target fabric
            
        Returns:
            True if sync should be triggered
        """
        # Check if event type triggers sync
        if provider == 'github' and event_type not in self.GITHUB_SYNC_EVENTS:
            return False
        
        if provider == 'gitlab' and event_type not in self.GITLAB_SYNC_EVENTS:
            return False
        
        # Check if the event affects the monitored branch
        target_branch = fabric.git_branch or 'main'
        
        if provider == 'github':
            if event_type == 'push':
                ref = payload.get('ref', '')
                push_branch = ref.replace('refs/heads/', '')
                return push_branch == target_branch
            
            elif event_type == 'pull_request':
                action = payload.get('action', '')
                if action in ['opened', 'synchronize', 'closed']:
                    pr_base = payload.get('pull_request', {}).get('base', {}).get('ref', '')
                    return pr_base == target_branch
        
        elif provider == 'gitlab':
            if event_type == 'Push Hook':
                ref = payload.get('ref', '')
                push_branch = ref.replace('refs/heads/', '')
                return push_branch == target_branch
            
            elif event_type == 'Merge Request Hook':
                action = payload.get('object_attributes', {}).get('action', '')
                if action in ['open', 'update', 'merge']:
                    mr_target = payload.get('object_attributes', {}).get('target_branch', '')
                    return mr_target == target_branch
        
        # Default to triggering sync for unknown scenarios
        return True


class WebhookSecurityValidator:
    """
    Validates webhook signatures and tokens for security.
    
    Supports GitHub HMAC-SHA256 signature validation and GitLab token validation.
    """
    
    def __init__(self):
        """Initialize webhook security validator."""
        self.logger = logging.getLogger(f"{__name__}.WebhookSecurityValidator")
    
    def validate_github_signature(
        self, 
        signature: str, 
        payload: bytes, 
        secret: str
    ) -> bool:
        """
        Validate GitHub webhook signature.
        
        Args:
            signature: GitHub signature header (X-Hub-Signature-256)
            payload: Raw webhook payload
            secret: Webhook secret
            
        Returns:
            True if signature is valid
        """
        if not signature.startswith('sha256='):
            self.logger.warning("GitHub signature does not start with 'sha256='")
            return False
        
        try:
            # Extract signature hash
            provided_signature = signature[7:]  # Remove 'sha256=' prefix
            
            # Calculate expected signature
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures using constant-time comparison
            is_valid = hmac.compare_digest(provided_signature, expected_signature)
            
            if not is_valid:
                self.logger.warning("GitHub webhook signature validation failed")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating GitHub signature: {e}")
            return False
    
    def validate_gitlab_token(self, token: str, secret: str) -> bool:
        """
        Validate GitLab webhook token.
        
        Args:
            token: GitLab token header (X-Gitlab-Token)
            secret: Webhook secret
            
        Returns:
            True if token is valid
        """
        try:
            # GitLab uses simple token comparison
            is_valid = hmac.compare_digest(token, secret)
            
            if not is_valid:
                self.logger.warning("GitLab webhook token validation failed")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating GitLab token: {e}")
            return False
    
    def validate_webhook_request(
        self, 
        request: HttpRequest, 
        fabric: HedgehogFabric
    ) -> Dict[str, Any]:
        """
        Validate webhook request and extract provider information.
        
        Args:
            request: Django HTTP request
            fabric: Target fabric with webhook configuration
            
        Returns:
            Dict with validation result and provider info
            
        Raises:
            WebhookSecurityError: If validation fails
        """
        # Determine provider from headers
        provider = self._detect_provider(request)
        
        if provider == 'github':
            return self._validate_github_webhook(request, fabric)
        elif provider == 'gitlab':
            return self._validate_gitlab_webhook(request, fabric)
        else:
            raise WebhookSecurityError(f"Unsupported webhook provider: {provider}")
    
    def _detect_provider(self, request: HttpRequest) -> str:
        """
        Detect Git provider from request headers.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Provider name ('github' or 'gitlab')
        """
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # GitHub webhooks have 'GitHub-Hookshot' in user agent
        if 'GitHub-Hookshot' in user_agent:
            return 'github'
        
        # GitLab webhooks have 'GitLab' in user agent or X-Gitlab-Event header
        if 'GitLab' in user_agent or 'HTTP_X_GITLAB_EVENT' in request.META:
            return 'gitlab'
        
        # Check for specific headers
        if 'HTTP_X_HUB_SIGNATURE_256' in request.META:
            return 'github'
        
        if 'HTTP_X_GITLAB_TOKEN' in request.META:
            return 'gitlab'
        
        raise WebhookSecurityError("Unable to detect webhook provider")
    
    def _validate_github_webhook(
        self, 
        request: HttpRequest, 
        fabric: HedgehogFabric
    ) -> Dict[str, Any]:
        """
        Validate GitHub webhook request.
        
        Args:
            request: Django HTTP request
            fabric: Target fabric
            
        Returns:
            Validation result with provider info
        """
        signature = request.META.get('HTTP_X_HUB_SIGNATURE_256')
        if not signature:
            raise WebhookSecurityError("Missing GitHub signature header")
        
        # Get webhook secret (could be configured per fabric)
        webhook_secret = getattr(fabric, 'webhook_secret', None)
        if not webhook_secret:
            # For development, allow unsigned webhooks
            if settings.DEBUG:
                self.logger.warning("GitHub webhook validation skipped (DEBUG mode)")
                return {
                    'valid': True,
                    'provider': 'github',
                    'event_type': request.META.get('HTTP_X_GITHUB_EVENT', 'unknown')
                }
            else:
                raise WebhookSecurityError("No webhook secret configured for fabric")
        
        # Validate signature
        if not self.validate_github_signature(signature, request.body, webhook_secret):
            raise WebhookSecurityError("GitHub signature validation failed")
        
        return {
            'valid': True,
            'provider': 'github',
            'event_type': request.META.get('HTTP_X_GITHUB_EVENT', 'unknown')
        }
    
    def _validate_gitlab_webhook(
        self, 
        request: HttpRequest, 
        fabric: HedgehogFabric
    ) -> Dict[str, Any]:
        """
        Validate GitLab webhook request.
        
        Args:
            request: Django HTTP request
            fabric: Target fabric
            
        Returns:
            Validation result with provider info
        """
        token = request.META.get('HTTP_X_GITLAB_TOKEN')
        if not token:
            raise WebhookSecurityError("Missing GitLab token header")
        
        # Get webhook secret
        webhook_secret = getattr(fabric, 'webhook_secret', None)
        if not webhook_secret:
            # For development, allow any token
            if settings.DEBUG:
                self.logger.warning("GitLab webhook validation skipped (DEBUG mode)")
                return {
                    'valid': True,
                    'provider': 'gitlab',
                    'event_type': request.META.get('HTTP_X_GITLAB_EVENT', 'unknown')
                }
            else:
                raise WebhookSecurityError("No webhook secret configured for fabric")
        
        # Validate token
        if not self.validate_gitlab_token(token, webhook_secret):
            raise WebhookSecurityError("GitLab token validation failed")
        
        return {
            'valid': True,
            'provider': 'gitlab',
            'event_type': request.META.get('HTTP_X_GITLAB_EVENT', 'unknown')
        }


# Global webhook processor instance
_webhook_processor = WebhookEventProcessor()


@csrf_exempt
@require_http_methods(["POST"])
async def webhook_handler(request: HttpRequest) -> JsonResponse:
    """
    Main webhook handler endpoint.
    
    Processes GitHub and GitLab webhook events with security validation
    and triggers appropriate GitOps synchronization operations.
    
    Args:
        request: Django HTTP request containing webhook payload
        
    Returns:
        JSON response with processing status
    """
    try:
        # Parse request body
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in webhook payload: {e}")
            return JsonResponse(
                {'error': 'Invalid JSON payload'}, 
                status=400
            )
        
        # Find fabric(s) that match this webhook
        fabrics = await _find_matching_fabrics(request, payload)
        
        if not fabrics:
            logger.warning("No matching fabrics found for webhook")
            return JsonResponse(
                {'error': 'No matching fabric found'}, 
                status=404
            )
        
        # Validate security for each fabric and process
        results = []
        
        for fabric in fabrics:
            try:
                # Validate webhook security
                validator = WebhookSecurityValidator()
                validation_result = validator.validate_webhook_request(request, fabric)
                
                # Queue webhook for async processing
                webhook_data = {
                    'fabric': fabric,
                    'provider': validation_result['provider'],
                    'event_type': validation_result['event_type'],
                    'payload': payload,
                    'timestamp': timezone.now()
                }
                
                # Ensure processor is running
                await _webhook_processor.start_processor()
                
                # Queue the webhook
                queued = await _webhook_processor.queue_webhook(webhook_data)
                
                if queued:
                    results.append({
                        'fabric': fabric.name,
                        'status': 'queued',
                        'event_type': validation_result['event_type']
                    })
                    logger.info(
                        f"Queued {validation_result['provider']} webhook "
                        f"for fabric {fabric.name}"
                    )
                else:
                    results.append({
                        'fabric': fabric.name,
                        'status': 'queue_failed',
                        'error': 'Failed to queue webhook for processing'
                    })
                
            except WebhookSecurityError as e:
                logger.warning(f"Webhook security validation failed for fabric {fabric.name}: {e}")
                results.append({
                    'fabric': fabric.name,
                    'status': 'rejected',
                    'error': f'Security validation failed: {str(e)}'
                })
            
            except Exception as e:
                logger.error(f"Error processing webhook for fabric {fabric.name}: {e}")
                results.append({
                    'fabric': fabric.name,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Return results
        overall_status = 'success' if any(r['status'] == 'queued' for r in results) else 'failed'
        
        return JsonResponse({
            'status': overall_status,
            'processed_fabrics': len(results),
            'results': results,
            'timestamp': timezone.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return JsonResponse(
            {'error': 'Internal server error'}, 
            status=500
        )


async def _find_matching_fabrics(
    request: HttpRequest, 
    payload: Dict[str, Any]
) -> List[HedgehogFabric]:
    """
    Find fabrics that match the webhook repository.
    
    Args:
        request: Django HTTP request
        payload: Webhook payload
        
    Returns:
        List of matching HedgehogFabric instances
    """
    # Extract repository URL from payload
    repo_url = _extract_repository_url(payload)
    
    if not repo_url:
        logger.warning("No repository URL found in webhook payload")
        return []
    
    # Find fabrics with matching Git repository URL
    try:
        matching_fabrics = await asyncio.to_thread(
            list,
            HedgehogFabric.objects.filter(
                git_repository_url=repo_url
            ).exclude(
                git_repository_url__isnull=True
            ).exclude(
                git_repository_url=''
            )
        )
        
        logger.debug(f"Found {len(matching_fabrics)} fabrics matching repository {repo_url}")
        return matching_fabrics
        
    except Exception as e:
        logger.error(f"Error finding matching fabrics: {e}")
        return []


def _extract_repository_url(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extract repository URL from webhook payload.
    
    Args:
        payload: Webhook payload
        
    Returns:
        Repository URL or None if not found
    """
    # GitHub payload structure
    if 'repository' in payload:
        repo_data = payload['repository']
        # Prefer HTTPS URL over SSH
        return (
            repo_data.get('clone_url') or 
            repo_data.get('html_url') or 
            repo_data.get('ssh_url')
        )
    
    # GitLab payload structure
    if 'project' in payload:
        project_data = payload['project']
        return (
            project_data.get('http_url') or
            project_data.get('web_url') or
            project_data.get('ssh_url')
        )
    
    # Alternative GitLab structure
    if 'repository' in payload and 'url' in payload['repository']:
        return payload['repository']['url']
    
    return None


async def webhook_status() -> JsonResponse:
    """
    Get webhook processor status.
    
    Returns:
        JSON response with processor status
    """
    try:
        queue_size = _webhook_processor._processing_queue.qsize()
        processor_running = (
            _webhook_processor._processor_task is not None and 
            not _webhook_processor._processor_task.done()
        )
        
        return JsonResponse({
            'processor_running': processor_running,
            'queue_size': queue_size,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        return JsonResponse(
            {'error': 'Failed to get status'}, 
            status=500
        )


# Webhook processor lifecycle management
async def start_webhook_processor():
    """Start the global webhook processor."""
    await _webhook_processor.start_processor()


async def stop_webhook_processor():
    """Stop the global webhook processor."""
    await _webhook_processor.stop_processor()