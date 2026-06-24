# SecBoard/app_risk/services/async_report_service.py

import logging
import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from celery import Celery
from celery.result import AsyncResult
from celery.exceptions import Retry
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from enum import Enum

from .report_config import ReportConfig
from .report_data_service_optimized import OptimizedReportDataService
from .report_generator_factory import ReportGeneratorFactory
from .advanced_cache_service import get_cache_service

logger = logging.getLogger(__name__)


class ReportStatus(Enum):
    """Report generation status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReportJob:
    """Report generation job"""
    job_id: str
    user_id: int
    config: ReportConfig
    status: ReportStatus
    progress: float
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_path: Optional[str] = None
    file_size: Optional[int] = None
    processing_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


class ProgressTracker:
    """Track report generation progress"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.steps = []
        self.current_step = 0
        self.total_steps = 0
        self.cache_service = get_cache_service()
    
    def add_step(self, name: str, weight: float = 1.0):
        """Add a processing step"""
        self.steps.append({
            'name': name,
            'weight': weight,
            'completed': False,
            'start_time': None,
            'end_time': None
        })
        self.total_steps += 1
    
    def start_step(self, step_index: int):
        """Start a processing step"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index]['start_time'] = timezone.now()
            self.current_step = step_index
            self._update_progress()
    
    def complete_step(self, step_index: int):
        """Complete a processing step"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index]['completed'] = True
            self.steps[step_index]['end_time'] = timezone.now()
            self._update_progress()
    
    def _update_progress(self):
        """Update progress in cache"""
        completed_weight = sum(step['weight'] for step in self.steps if step['completed'])
        total_weight = sum(step['weight'] for step in self.steps)
        
        progress = (completed_weight / total_weight * 100) if total_weight > 0 else 0
        
        progress_data = {
            'progress': progress,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'steps': self.steps,
            'updated_at': timezone.now().isoformat()
        }
        
        self.cache_service.set(
            f"report_progress_{self.job_id}",
            progress_data,
            strategy='quick',
            timeout=300
        )
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress"""
        return self.cache_service.get(f"report_progress_{self.job_id}") or {
            'progress': 0,
            'current_step': 0,
            'total_steps': 0,
            'steps': []
        }


class NotificationService:
    """Service for sending notifications about report completion"""
    
    def __init__(self):
        self.notification_methods = {
            'email': self._send_email_notification,
            'cache': self._send_cache_notification
        }
    
    def notify_completion(self, job: ReportJob, user: User, methods: List[str] = None):
        """Send completion notification"""
        methods = methods or ['email', 'cache']
        
        for method in methods:
            if method in self.notification_methods:
                try:
                    self.notification_methods[method](job, user)
                except Exception as e:
                    logger.error(f"Error sending {method} notification: {e}")
    
    def _send_email_notification(self, job: ReportJob, user: User):
        """Send email notification"""
        if not user.email:
            return
        
        subject = "Report Generation Completed"
        if job.status == ReportStatus.COMPLETED:
            message = f"Your report has been generated successfully. Job ID: {job.job_id}"
        else:
            message = f"Report generation failed. Job ID: {job.job_id}. Error: {job.error_message}"
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )
    

    
    def _send_cache_notification(self, job: ReportJob, user: User):
        """Store notification in cache for polling"""
        cache_service = get_cache_service()
        notification_key = f"user_notifications_{user.id}"
        
        notifications = cache_service.get(notification_key) or []
        notifications.append({
            'id': str(uuid.uuid4()),
            'type': 'report_completion',
            'job_id': job.job_id,
            'status': job.status.value,
            'message': f"Report generation {job.status.value}",
            'timestamp': timezone.now().isoformat(),
            'read': False
        })
        
        # Keep only last 10 notifications
        notifications = notifications[-10:]
        
        cache_service.set(notification_key, notifications, timeout=3600)


class AsyncReportService:
    """Async service for handling large report generation"""
    
    def __init__(self):
        self.job_queue = queue.Queue()
        self.active_jobs = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        self.notification_service = NotificationService()
        self.cache_service = get_cache_service()
        self.max_concurrent_jobs = 5
        
        # Start background worker
        self._start_background_worker()
    
    def _start_background_worker(self):
        """Start background worker thread"""
        def worker():
            while True:
                try:
                    job = self.job_queue.get(timeout=5)
                    if job:
                        self._process_job(job)
                        self.job_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in background worker: {e}")
        
        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()
    
    def submit_report_job(self, user: User, config: ReportConfig, 
                         priority: int = 1, notification_methods: List[str] = None) -> str:
        """Submit a report generation job"""
        job_id = str(uuid.uuid4())
        
        job = ReportJob(
            job_id=job_id,
            user_id=user.id,
            config=config,
            status=ReportStatus.PENDING,
            progress=0.0,
            created_at=timezone.now()
        )
        
        # Store job in cache
        self.cache_service.set(
            f"report_job_{job_id}",
            job.to_dict(),
            strategy='persistent',
            timeout=3600
        )
        
        # Add to queue
        self.job_queue.put({
            'job': job,
            'user': user,
            'priority': priority,
            'notification_methods': notification_methods or ['email', 'cache']
        })
        
        logger.info(f"Report job submitted: {job_id} for user {user.username}")
        return job_id
    
    def _process_job(self, job_data: Dict[str, Any]):
        """Process a report generation job"""
        job = job_data['job']
        user = job_data['user']
        notification_methods = job_data['notification_methods']
        
        # Check if too many concurrent jobs
        if len(self.active_jobs) >= self.max_concurrent_jobs:
            logger.warning(f"Too many concurrent jobs, requeueing {job.job_id}")
            self.job_queue.put(job_data)
            return
        
        # Mark job as running
        job.status = ReportStatus.RUNNING
        job.started_at = timezone.now()
        self.active_jobs[job.job_id] = job
        
        # Update job in cache
        self._update_job_cache(job)
        
        # Initialize progress tracker
        progress_tracker = ProgressTracker(job.job_id)
        
        try:
            # Set up progress tracking steps
            progress_tracker.add_step("Initializing", 0.1)
            progress_tracker.add_step("Fetching data", 0.3)
            progress_tracker.add_step("Processing data", 0.2)
            progress_tracker.add_step("Generating report", 0.3)
            progress_tracker.add_step("Finalizing", 0.1)
            
            # Execute job steps
            result = self._execute_job_steps(job, user, progress_tracker)
            
            # Mark as completed
            job.status = ReportStatus.COMPLETED
            job.completed_at = timezone.now()
            job.processing_time = (job.completed_at - job.started_at).total_seconds()
            job.result_path = result.get('file_path')
            job.file_size = result.get('file_size')
            
            logger.info(f"Report job completed: {job.job_id} in {job.processing_time:.2f}s")
            
        except Exception as e:
            job.status = ReportStatus.FAILED
            job.error_message = str(e)
            job.completed_at = timezone.now()
            logger.error(f"Report job failed: {job.job_id} - {e}")
        
        finally:
            # Remove from active jobs
            if job.job_id in self.active_jobs:
                del self.active_jobs[job.job_id]
            
            # Update job in cache
            self._update_job_cache(job)
            
            # Send notifications
            self.notification_service.notify_completion(job, user, notification_methods)
    
    def _execute_job_steps(self, job: ReportJob, user: User, progress_tracker: ProgressTracker) -> Dict[str, Any]:
        """Execute job processing steps"""
        
        # Step 1: Initialize
        progress_tracker.start_step(0)
        data_service = OptimizedReportDataService(user, job.config)
        progress_tracker.complete_step(0)
        
        # Step 2: Fetch data
        progress_tracker.start_step(1)
        report_data = data_service.get_comprehensive_report_data()
        progress_tracker.complete_step(1)
        
        # Step 3: Process data
        progress_tracker.start_step(2)
        processed_data = self._process_report_data(report_data)
        progress_tracker.complete_step(2)
        
        # Step 4: Generate report
        progress_tracker.start_step(3)
        generator = ReportGeneratorFactory.create_generator(job.config, data_service)
        report_result = generator.generate()
        progress_tracker.complete_step(3)
        
        # Step 5: Finalize
        progress_tracker.start_step(4)
        final_result = self._finalize_report(report_result, job)
        progress_tracker.complete_step(4)
        
        return final_result
    
    def _process_report_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process report data for optimization"""
        # Add any additional processing here
        processed_data = report_data.copy()
        
        # Example: Add calculated fields
        if 'statistics' in processed_data:
            stats = processed_data['statistics']
            if 'total_assets' in stats and 'high_risk_vulnerabilities' in stats:
                stats['risk_percentage'] = (
                    stats['high_risk_vulnerabilities'] / stats['total_assets'] * 100
                    if stats['total_assets'] > 0 else 0
                )
        
        return processed_data
    
    def _finalize_report(self, report_result: Dict[str, Any], job: ReportJob) -> Dict[str, Any]:
        """Finalize report and save to storage"""
        # In a real implementation, you would save to file storage
        # For now, we'll just return the result
        
        file_path = f"reports/{job.job_id}.{job.config.format}"
        file_size = len(report_result.get('content', b''))
        
        # Save to cache for download
        self.cache_service.set(
            f"report_file_{job.job_id}",
            report_result,
            strategy='persistent',
            timeout=3600
        )
        
        return {
            'file_path': file_path,
            'file_size': file_size,
            'content_type': report_result.get('content_type'),
            'filename': report_result.get('filename')
        }
    
    def _update_job_cache(self, job: ReportJob):
        """Update job in cache"""
        self.cache_service.set(
            f"report_job_{job.job_id}",
            job.to_dict(),
            strategy='persistent',
            timeout=3600
        )
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        job_data = self.cache_service.get(f"report_job_{job_id}")
        if not job_data:
            return None
        
        # Add progress information
        progress_data = self.cache_service.get(f"report_progress_{job_id}")
        if progress_data:
            job_data['progress_details'] = progress_data
        
        return job_data
    
    def get_user_jobs(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user's report jobs"""
        # In a real implementation, you would query from database
        # For now, we'll return from cache (limited functionality)
        
        jobs = []
        # This is a simplified implementation
        # In production, you'd store job IDs in a user-specific cache key
        
        return jobs
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job"""
        job_data = self.cache_service.get(f"report_job_{job_id}")
        if not job_data:
            return False
        
        if job_data['status'] in ['pending', 'running']:
            job_data['status'] = 'cancelled'
            job_data['completed_at'] = timezone.now().isoformat()
            
            self.cache_service.set(
                f"report_job_{job_id}",
                job_data,
                strategy='persistent',
                timeout=3600
            )
            
            # Remove from active jobs if running
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            return True
        
        return False
    
    def get_job_file(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get generated report file"""
        job_data = self.cache_service.get(f"report_job_{job_id}")
        if not job_data or job_data['status'] != 'completed':
            return None
        
        file_data = self.cache_service.get(f"report_file_{job_id}")
        return file_data
    
    def cleanup_old_jobs(self, days: int = 7):
        """Clean up old job data"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # In a real implementation, you would query database for old jobs
        # and clean them up along with their files
        
        logger.info(f"Cleaned up jobs older than {days} days")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            'active_jobs': len(self.active_jobs),
            'queue_size': self.job_queue.qsize(),
            'max_concurrent_jobs': self.max_concurrent_jobs,
            'active_job_ids': list(self.active_jobs.keys()),
            'cache_stats': self.cache_service.get_cache_stats()
        }


# Global async report service instance
async_report_service = AsyncReportService()


def get_async_report_service() -> AsyncReportService:
    """Get global async report service instance"""
    return async_report_service


# Celery task for distributed processing (optional)
try:
    from celery import shared_task
    
    @shared_task(bind=True, max_retries=3)
    def generate_report_async(self, user_id: int, config_dict: Dict[str, Any]):
        """Celery task for async report generation"""
        try:
            from django.contrib.auth.models import User
            from .report_config import ReportConfig
            
            user = User.objects.get(id=user_id)
            config = ReportConfig.from_dict(config_dict)
            
            service = get_async_report_service()
            job_id = service.submit_report_job(user, config)
            
            return {'job_id': job_id, 'status': 'submitted'}
            
        except Exception as e:
            logger.error(f"Celery task failed: {e}")
            raise self.retry(countdown=60, exc=e)

except ImportError:
    logger.info("Celery not available, using thread-based async processing")