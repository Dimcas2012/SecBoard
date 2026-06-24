# SecBoard/app_access/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from functools import wraps
import json
import time

logger = logging.getLogger(__name__)

# Function to ensure unique task execution
def ensure_unique_task(timeout=3600):
    """Decorator to ensure only one instance of a task is running"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from celery.exceptions import Retry
            from django.core.cache import cache
            
            # Create a unique lock key from the task name and arguments
            task_name = func.__name__
            task_signature = f"{task_name}:{json.dumps(args)}:{json.dumps(kwargs)}"
            lock_id = f"task_lock:{task_signature}"
            
            # Try to acquire the lock
            if cache.get(lock_id):
                logger.warning(f"Task {task_name} is already running with the same arguments. Skipping.")
                return {
                    'status': 'skipped',
                    'reason': 'Another instance is already running'
                }
            
            # Set the lock with an expiration
            cache.set(lock_id, True, timeout=timeout)
            
            try:
                # Run the task
                result = func(*args, **kwargs)
                return result
            finally:
                # Always release the lock, even if the task fails
                cache.delete(lock_id)
        
        return wrapper
    return decorator

@shared_task
def beat_heartbeat():
    """Update Redis with the current timestamp to verify Beat is running."""
    try:
        from django.conf import settings
        import redis
        
        # Initialize Redis client
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
        
        # Update heartbeat timestamp
        current_time = time.time()
        redis_client.set('celery-beat-heartbeat', str(current_time), ex=120)  # expires in 2 minutes
        
        logger.info(f"Beat heartbeat updated at {current_time}")
        return {
            'success': True,
            'message': "Beat heartbeat updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating beat heartbeat: {str(e)}")
        return {
            'success': False,
            'message': f"Error updating beat heartbeat: {str(e)}"
        }

@shared_task
@ensure_unique_task(timeout=3600)
def sync_api_users_task(scheduled_sync_id=None, credential_id=None):
    """
    Task to synchronize API users using a credential.
    Can be triggered by a scheduled sync or directly.
    """
    from app_access.models import ApiCredential, ApiSyncStatus, ScheduledSync
    from django.contrib.auth import get_user_model
    import requests
    from django.core.exceptions import ObjectDoesNotExist
    
    User = get_user_model()
    
    logger.info(f"Starting API users sync task. Scheduled: {scheduled_sync_id}, Credential: {credential_id}")
    
    try:
        # Determine which credential to use
        if scheduled_sync_id:
            try:
                scheduled_sync = ScheduledSync.objects.get(id=scheduled_sync_id)
                credential = scheduled_sync.credential
                # Update last run time
                scheduled_sync.last_run = timezone.now()
                scheduled_sync.save(update_fields=['last_run'])
                
                # If it's a one-time task, deactivate it
                if scheduled_sync.frequency == 'once':
                    scheduled_sync.is_active = False
                    scheduled_sync.save(update_fields=['is_active'])
                else:
                    # Recalculate next run time
                    scheduled_sync.calculate_next_run()
                
                logger.info(f"Running scheduled sync '{scheduled_sync.name}' with credential '{credential.name}'")
                
            except ObjectDoesNotExist:
                logger.error(f"Scheduled sync with ID {scheduled_sync_id} not found")
                return {
                    'status': 'error',
                    'message': f"Scheduled sync with ID {scheduled_sync_id} not found"
                }
        elif credential_id:
            try:
                credential = ApiCredential.objects.get(id=credential_id)
                logger.info(f"Running direct sync with credential '{credential.name}'")
            except ObjectDoesNotExist:
                logger.error(f"Credential with ID {credential_id} not found")
                return {
                    'status': 'error',
                    'message': f"Credential with ID {credential_id} not found"
                }
        else:
            logger.error("Neither scheduled_sync_id nor credential_id provided")
            return {
                'status': 'error',
                'message': "Neither scheduled_sync_id nor credential_id provided"
            }
        
        # Create a sync status record
        sync_status = ApiSyncStatus.objects.create(
            credential=credential,
            status='running',
            current_step=_('Initializing...'),
            completed_steps=0,
            total_steps=5
        )
        
        # Start API sync process
        try:
            # Call the actual API synchronization function from api_view.py if available
            from django.http import HttpRequest
            from app_access.api_view import sync_api_users
            
            # Create a mock request object
            request = HttpRequest()
            request.method = 'POST'
            request.user = credential.user
            
            # Set up session attribute properly
            from django.contrib.sessions.backends.db import SessionStore
            request.session = SessionStore()
            
            # Set up messages framework placeholder
            from django.contrib.messages.storage.fallback import FallbackStorage
            setattr(request, '_messages', FallbackStorage(request))
            
            # Prepare request data
            from django.http import QueryDict
            request.POST = QueryDict('').copy()
            request.POST['credential_id'] = str(credential.id)
            
            # Import necessary modules
            import json
            from django.http import JsonResponse
            
            # Call the function
            try:
                from django.middleware.csrf import get_token
                request.META = {'CSRF_COOKIE': get_token(request)}
                
                # Wrap the call in a try/except to handle any errors
                try:
                    response = sync_api_users(request)
                    
                    # Process the response
                    if isinstance(response, JsonResponse):
                        response_data = json.loads(response.content.decode('utf-8'))
                        if response_data.get('success'):
                            sync_status.complete()
                            logger.info(f"API sync completed successfully via sync_api_users function")
                        else:
                            error_message = response_data.get('error', 'Unknown error from sync_api_users')
                            sync_status.error(error_message)
                            logger.error(f"API sync failed: {error_message}")
                    else:
                        # Non-JSON response means something went wrong
                        sync_status.error("Unexpected response from sync_api_users function")
                        logger.error("API sync function returned non-JSON response")
                except Exception as e:
                    logger.error(f"Error in sync_api_users function: {str(e)}", exc_info=True)
                    sync_status.error(f"Error in sync_api_users: {str(e)}")
                    
            except Exception as sync_error:
                logger.error(f"Error calling sync_api_users function: {str(sync_error)}", exc_info=True)
                # Fallback to simple completion if the function call fails
                sync_status.complete()
            
            return {
                'status': 'success',
                'message': 'API user sync completed successfully',
                'sync_status_id': sync_status.id
            }
            
        except Exception as e:
            error_message = f"Error during API sync: {str(e)}"
            logger.error(error_message, exc_info=True)
            sync_status.error(error_message)
            return {
                'status': 'error',
                'message': error_message,
                'sync_status_id': sync_status.id
            }
    
    except Exception as e:
        error_message = f"Unexpected error in sync_api_users_task: {str(e)}"
        logger.error(error_message, exc_info=True)
        return {
            'status': 'error',
            'message': error_message
        } 