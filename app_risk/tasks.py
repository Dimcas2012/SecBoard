from celery import shared_task, Task
from django.utils import timezone
from django.utils.translation import gettext as _
from django.conf import settings
import logging
import os
from datetime import datetime, timedelta
import json
import traceback
from typing import Dict, Any, Optional
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.cache import cache

from .models import ScheduledReport, ScheduledReportExecution, RiskReportEmailConfig
from .services import (
    ReportConfig,
    OptimizedReportDataService,
    get_cache_service,
    get_performance_monitor_service,
    add_metric,
    monitor_operation
)
from .report_views import generate_report_file
from django.utils.translation import activate
from celery.schedules import crontab

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def check_scheduled_reports(self):
    """
    Check for scheduled reports that need to be executed
    This task should run every minute
    """
    try:
        now = timezone.now()
        logger.info(f"=" * 80)
        logger.info(f"Checking scheduled reports at {now} (UTC) / {now.astimezone()} (local)")
        logger.info(f"=" * 80)
        
        # Find reports that are due for execution
        due_reports = ScheduledReport.objects.filter(
            status='active',
            next_run__lte=now,
            next_run__isnull=False
        )
        
        # Log all active reports for debugging
        all_active_reports = ScheduledReport.objects.filter(status='active', next_run__isnull=False)
        logger.info(f"📊 Found {all_active_reports.count()} active reports with next_run set:")
        for r in all_active_reports:
            is_due = r.next_run <= now if r.next_run else False
            time_diff = (r.next_run - now).total_seconds() if r.next_run and r.next_run > now else 0
            time_diff_minutes = time_diff / 60 if time_diff > 0 else 0
            status_icon = "✅" if is_due else "⏳"
            logger.info(
                f"  {status_icon} {r.name} (ID: {r.id}): "
                f"next_run={r.next_run} (UTC) / {r.next_run.astimezone() if r.next_run else 'N/A'} (local), "
                f"frequency={r.frequency}, run_count={r.run_count}, "
                f"due={is_due}, "
                f"{f'time_until={time_diff_minutes:.1f}min' if time_diff_minutes > 0 else 'OVERDUE' if is_due else 'future'}"
            )
        
        # Log reports with next_run in the near future (within 5 minutes) for monitoring
        from datetime import timedelta
        near_future = now + timedelta(minutes=5)
        near_future_reports = ScheduledReport.objects.filter(
            status='active',
            next_run__gt=now,
            next_run__lte=near_future,
            next_run__isnull=False
        )
        if near_future_reports.exists():
            logger.info(f"⏰ Found {near_future_reports.count()} reports scheduled in the next 5 minutes:")
            for r in near_future_reports:
                time_diff = (r.next_run - now).total_seconds() / 60
                logger.info(
                    f"  ⏰ {r.name} (ID: {r.id}): "
                    f"next_run={r.next_run.astimezone()} (local), "
                    f"in {time_diff:.1f} minutes"
                )
        
        # Log reports with inactive status but next_run in the past (potential issues)
        inactive_past_reports = ScheduledReport.objects.filter(
            status__in=['paused', 'completed'],
            next_run__lte=now,
            next_run__isnull=False
        )
        if inactive_past_reports.exists():
            logger.warning(f"⚠️  Found {inactive_past_reports.count()} inactive reports with past next_run (potential issues):")
            for r in inactive_past_reports:
                logger.warning(
                    f"  ⚠️  {r.name} (ID: {r.id}): "
                    f"status={r.status}, next_run={r.next_run.astimezone()} (local), "
                    f"frequency={r.frequency}, run_count={r.run_count}"
                )
        
        logger.info(f"🔍 Found {due_reports.count()} reports due for execution:")
        if due_reports.exists():
            for r in due_reports:
                overdue_minutes = (now - r.next_run).total_seconds() / 60 if r.next_run else 0
                logger.info(
                    f"  ✅ {r.name} (ID: {r.id}): "
                    f"next_run={r.next_run.astimezone()} (local), "
                    f"frequency={r.frequency}, run_count={r.run_count}, "
                    f"overdue_by={overdue_minutes:.1f} minutes"
                )
        else:
            logger.info("  (No reports due for execution)")
        
        executed_count = 0
        skipped_count = 0
        error_count = 0
        
        for report in due_reports:
            try:
                # Check if there's already a pending or running execution
                existing_execution = ScheduledReportExecution.objects.filter(
                    scheduled_report=report,
                    status__in=['pending', 'running']
                ).first()
                
                if existing_execution:
                    logger.warning(
                        f"⏸️  Skipping report {report.name} (ID: {report.id}) - "
                        f"already has execution in progress: "
                        f"execution_id={existing_execution.id}, "
                        f"status={existing_execution.status}, "
                        f"started_at={existing_execution.started_at.astimezone() if existing_execution.started_at else 'N/A'}"
                    )
                    skipped_count += 1
                    continue
                
                # Execute the report
                logger.info(
                    f"🚀 Triggering execution for report: {report.name} "
                    f"(ID: {report.id}, next_run: {report.next_run.astimezone()} local, "
                    f"frequency: {report.frequency}, run_count: {report.run_count})"
                )
                task_result = execute_scheduled_report.delay(str(report.id))
                executed_count += 1
                logger.info(
                    f"✅ Successfully triggered execution for report: {report.name} "
                    f"(task_id: {task_result.id})"
                )
                
            except Exception as e:
                error_count += 1
                logger.error(
                    f"❌ Error triggering execution for report {report.name} (ID: {report.id}): {str(e)}",
                    exc_info=True
                )
        
        logger.info(f"=" * 80)
        logger.info(
            f"📈 Summary: "
            f"Total due: {due_reports.count()}, "
            f"Executed: {executed_count}, "
            f"Skipped: {skipped_count}, "
            f"Errors: {error_count}"
        )
        logger.info(f"=" * 80)
        
        return f"Triggered {executed_count} scheduled report executions"
        
    except Exception as e:
        logger.error(f"❌ Error in check_scheduled_reports: {str(e)}", exc_info=True)
        raise


@shared_task(bind=True)
def execute_scheduled_report(self, report_id, manual_execution=False):
    """
    Execute a specific scheduled report
    
    Args:
        report_id: ID of the scheduled report
        manual_execution: Whether this is a manual execution (True) or scheduled execution (False)
    """
    execution_start_time = timezone.now()
    try:
        # Get the scheduled report
        try:
            report = ScheduledReport.objects.get(id=report_id)
        except ScheduledReport.DoesNotExist:
            logger.error(f"❌ Scheduled report with ID {report_id} not found")
            return f"Report {report_id} not found"
        
        # Log execution type
        execution_type = "manual" if manual_execution else "scheduled"
        logger.info(f"=" * 80)
        logger.info(
            f"🚀 Starting {execution_type} execution of scheduled report: "
            f"{report.name} (ID: {report.id})"
        )
        logger.info(
            f"📋 Report details: "
            f"frequency={report.frequency}, "
            f"status={report.status}, "
            f"next_run={report.next_run.astimezone() if report.next_run else 'None'} (local), "
            f"run_count={report.run_count}, "
            f"start_date={report.start_date}, "
            f"execution_time={report.execution_time}"
        )
        logger.info(f"⏰ Execution started at: {execution_start_time.astimezone()} (local)")
        
        # Create execution record
        execution = ScheduledReportExecution.objects.create(
            scheduled_report=report,
            status='running'
        )
        logger.info(f"✅ Created execution record (ID: {execution.id}, status: {execution.status})")
        
        try:
            # Generate the report - use ReportProfile settings if available
            if report.report_profile:
                logger.info(f"Using ReportProfile settings for scheduled report: {report.name}")
                user = report.created_by
                
                # Create a mock request for report generation
                from django.http import HttpRequest, QueryDict
                from .report_views import generate_risk_report_from_profile
                
                request = HttpRequest()
                request.method = 'POST'
                request.user = user
                request.META = {
                    'SERVER_NAME': 'localhost',
                    'SERVER_PORT': '8000',
                    'HTTP_HOST': 'localhost:8000',
                    'wsgi.url_scheme': 'http',
                }
                # Set language for the request
                request.LANGUAGE_CODE = report.report_profile.default_language
                post_data = QueryDict(mutable=True)
                post_data['profile_id'] = str(report.report_profile.id)
                request.POST = post_data
                
                # Instead of producing a file, generate HTML snapshot
                from .report_views import generate_report_data, generate_html_preview
                # Build params from profile
                sections_config = report.report_profile.get_sections_config()
                company_id = sections_config.get('_company_id', '')
                # Build profile header dict for unified generator
                company_name = 'All Companies'
                if company_id:
                    try:
                        from app_cabinet.models import Company
                        company = Company.objects.get(id=company_id)
                        company_name = company.name
                    except Exception:
                        pass
                profile_info = {
                    'name': report.report_profile.name,
                    'description': report.report_profile.description,
                    'created_by': report.report_profile.created_by.get_full_name() or report.report_profile.created_by.username,
                    'created_at': report.report_profile.created_at,
                    'company': company_name,
                }
                params = {
                    'reportType': 'profile',
                    'format': 'html',
                    'language': report.report_profile.default_language,
                    'company_id': str(company_id) if company_id else '',
                    'selectedSections': sections_config,
                    'profile': profile_info,
                }
                logger.info(f"📊 Generating report data for: {report.name}")
                report_data = generate_report_data(report.created_by, params)
                logger.info(f"✅ Report data generated successfully")
                
                logger.info(f"📄 Generating HTML preview for: {report.name}")
                preview_html = generate_html_preview(report_data, 'profile', report.report_profile.default_language, sections_config)
                execution.snapshot_html = preview_html
                execution.snapshot_language = report.report_profile.default_language
                execution.snapshot_created_at = timezone.now()
                execution.save()
                logger.info(f"✅ HTML snapshot generated and saved (size: {len(preview_html)} chars)")
            else:
                logger.info(f"📋 Using individual settings for scheduled report: {report.name}")
                report_data = {
                    'reportType': report.report_type,
                    'reportFormat': report.report_format,
                    'reportLanguage': report.report_language,
                    'reportCompany': report.company.id if report.company else '',
                    'reportNotes': f'Automatically generated report - {report.name}'
                }
                logger.info(f"📊 Generating report file for: {report.name}")
                file_path, file_size = generate_report_file(report_data)
                logger.info(f"✅ Report file generated: {file_path} (size: {file_size} bytes)")
            
            # Mark execution completed (no file path in link mode)
            execution.file_path = ''
            execution.file_size = None
            execution.status = 'completed'
            execution.completed_at = timezone.now()
            execution.save()
            logger.info(f"✅ Execution marked as completed (execution ID: {execution.id})")
            
            # Send email if configured
            # Use global Risk Report Email Settings exclusively for sending
            global_cfg = RiskReportEmailConfig.objects.first()
            if global_cfg and global_cfg.send_email:
                try:
                    # Send email with link instead of attachment
                    from django.conf import settings
                    # Build absolute URL without request context
                    def _build_absolute_url(path: str) -> str:
                        # Try to get Site Domain from SiteSettings (primary source)
                        try:
                            from app_conf.models import SiteSettings
                            site_settings = SiteSettings.get_settings()
                            logger.info(f"[execute_scheduled_report] SiteSettings loaded: site_domain='{site_settings.site_domain if site_settings else 'None'}', site_protocol='{site_settings.site_protocol if site_settings else 'None'}'")
                            
                            if site_settings and site_settings.site_domain and site_settings.site_domain.strip():
                                # Use get_site_url() method which combines protocol + domain
                                base = site_settings.get_site_url().rstrip('/')
                                logger.info(f"[execute_scheduled_report] Using Site Domain from SiteSettings: {base} for path: {path}")
                                full_url = f"{base}{path}"
                                logger.info(f"[execute_scheduled_report] Generated full URL: {full_url}")
                                return full_url
                            else:
                                logger.warning(f"[execute_scheduled_report] SiteSettings.site_domain is empty or None: site_settings={site_settings}, site_domain='{site_settings.site_domain if site_settings else 'No SiteSettings'}'")
                        except Exception as e:
                            logger.error(f"[execute_scheduled_report] Could not load SiteSettings: {e}", exc_info=True)
                        
                        # Fallback to PUBLIC_BASE_URL from settings
                        base = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
                        if base:
                            logger.warning(f"[execute_scheduled_report] Using PUBLIC_BASE_URL fallback: {base} for path: {path}")
                            return f"{base}{path}"
                        
                        # Fallback to ALLOWED_HOSTS - but prefer test.secboard.online if available
                        scheme = 'https' if getattr(settings, 'PRODUCTION', False) else 'http'
                        host = 'localhost:8000'
                        try:
                            if settings.ALLOWED_HOSTS:
                                # Prefer test.secboard.online if available, otherwise use first non-testserver host
                                preferred_hosts = ['test.secboard.online', 'demo.secboard.online', 'prod.secboard.online', 'secboard.online']
                                host = None
                                for preferred in preferred_hosts:
                                    if preferred in settings.ALLOWED_HOSTS:
                                        host = preferred
                                        break
                                if not host:
                                    host = next((h for h in settings.ALLOWED_HOSTS if h not in ('testserver',)), settings.ALLOWED_HOSTS[0])
                                if ':' not in host and host in ('localhost', '127.0.0.1'):
                                    host = f"{host}:8000"
                        except Exception:
                            pass
                        fallback_url = f"{scheme}://{host}"
                        logger.warning(f"[execute_scheduled_report] Using ALLOWED_HOSTS fallback: {fallback_url} for path: {path}")
                        return f"{fallback_url}{path}"

                    snapshot_path = execution.get_snapshot_url()
                    link_url = _build_absolute_url(snapshot_path)
                    
                    # Use ScheduledReport's custom email settings if available, otherwise fall back to global settings
                    if report.email_subject and report.email_subject.strip():
                        subject = report.email_subject
                    else:
                        subject = (global_cfg.default_subject or 'Risk Assessment Report')
                    
                    if report.email_body and report.email_body.strip():
                        # Process email body with tags
                        body = report.process_email_tags(report.email_body, execution)
                    else:
                        body_text = (global_cfg.default_body or 'Please view your report at the link below.')
                        body = body_text + f"\n\n{link_url}"

                    # Collect recipients
                    recipients = [u.user.email for u in report.email_recipients.all() if u.user and u.user.email]
                    if not recipients:
                        logger.warning(f"No valid recipients for report: {report.name}")
                        email_sent = False
                    else:
                        # Prefer custom Mail Account when default settings are disabled
                        # Prefer global mail account if configured; otherwise use Django backend
                        selected_account = global_cfg.mail_account if global_cfg and global_cfg.mail_account else None

                        if selected_account:
                            try:
                                import smtplib
                                import ssl
                                from email.mime.multipart import MIMEMultipart
                                from email.mime.text import MIMEText

                                smtp_host = selected_account.server.smtp_host
                                smtp_port = selected_account.server.smtp_port
                                use_ssl = getattr(selected_account.server, 'use_ssl', False)
                                use_tls = getattr(selected_account.server, 'use_tls', False)
                                username = selected_account.username
                                password = selected_account.password

                                msg = MIMEMultipart()
                                msg['From'] = username
                                msg['To'] = ', '.join(recipients)
                                msg['Subject'] = subject
                                msg.attach(MIMEText(body, 'plain'))

                                if use_ssl:
                                    context = ssl.create_default_context()
                                    context.check_hostname = False
                                    context.verify_mode = ssl.CERT_NONE
                                    server = smtplib.SMTP_SSL(host=smtp_host, port=smtp_port, context=context)
                                else:
                                    server = smtplib.SMTP(host=smtp_host, port=smtp_port)
                                    if use_tls:
                                        server.starttls()

                                server.login(username, password)
                                server.send_message(msg)
                                server.quit()
                                email_sent = True
                            except Exception as smtp_err:
                                logger.error(f"Direct SMTP send failed for report {report.name}: {smtp_err}")
                                email_sent = False
                        else:
                            # Fallback to Django email backend
                            from django.core.mail import EmailMessage
                            from_email = global_cfg.mail_account.username if (global_cfg and global_cfg.mail_account) else None
                            email = EmailMessage(subject=subject, body=body, from_email=from_email, to=recipients)
                            email.send(fail_silently=False)
                            email_sent = True

                    # Update execution email status
                    if email_sent:
                        execution.email_sent = True
                        execution.email_recipients_count = len(recipients)
                        execution.save()
                        logger.info(
                            f"✅ Email sent successfully for report: {report.name} "
                            f"to {len(recipients)} recipient(s): {', '.join(recipients)}"
                        )
                    else:
                        logger.warning(
                            f"⚠️  Email was not sent for report: {report.name} "
                            f"(recipients: {len(recipients) if recipients else 0})"
                        )
                except Exception as e:
                    logger.error(f"Error sending email for report {report.name}: {str(e)}", exc_info=True)
                    execution.email_error = str(e)
                    execution.save()
            else:
                logger.info("Global Risk Report Email Settings disabled or not configured; skipping email send for scheduled report")
            
            # Update report statistics
            execution_end_time = timezone.now()
            execution_duration = (execution_end_time - execution_start_time).total_seconds()
            
            report.last_run = execution_end_time
            report.run_count += 1
            
            # Only update next_run for scheduled executions, not manual ones
            if not manual_execution:
                # If it's a "once" frequency, mark as completed and set next_run to None
                if report.frequency == 'once':
                    old_status = report.status
                    old_next_run = report.next_run
                    report.status = 'completed'
                    report.next_run = None  # Once executed, no more runs
                    logger.info(
                        f"🔄 Updated report {report.name}: "
                        f"status={old_status} -> {report.status}, "
                        f"next_run={old_next_run.astimezone() if old_next_run else 'None'} -> None "
                        f"(once frequency, no more runs)"
                    )
                else:
                    # Calculate next run for recurring reports
                    old_next_run = report.next_run
                    report.next_run = report.calculate_next_run()
                    logger.info(
                        f"🔄 Updated next_run for report {report.name}: "
                        f"{old_next_run.astimezone() if old_next_run else 'None'} -> "
                        f"{report.next_run.astimezone() if report.next_run else 'None'} (local)"
                    )
            
            report.save()
            logger.info(
                f"💾 Saved report {report.name}: "
                f"status={report.status}, "
                f"next_run={report.next_run.astimezone() if report.next_run else 'None'} (local), "
                f"run_count={report.run_count}, "
                f"last_run={report.last_run.astimezone() if report.last_run else 'None'} (local)"
            )
            
            # Mark execution as completed
            execution.status = 'completed'
            execution.completed_at = execution_end_time
            execution.save()
            
            logger.info(f"=" * 80)
            logger.info(
                f"✅ Successfully executed {execution_type} report: {report.name} "
                f"(duration: {execution_duration:.2f}s)"
            )
            logger.info(f"=" * 80)
            
            return f"Successfully executed report: {report.name}"
            
        except Exception as e:
            # Update execution with error
            execution_end_time = timezone.now()
            execution_duration = (execution_end_time - execution_start_time).total_seconds()
            
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = execution_end_time
            execution.save()
            
            logger.error(f"=" * 80)
            logger.error(
                f"❌ Failed to execute {execution_type} report: {report.name} "
                f"(duration: {execution_duration:.2f}s)"
            )
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"=" * 80)
            
            # Update report status
            report.status = 'failed'
            report.save()
            
            logger.error(f"Error executing scheduled report {report.name}: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in execute_scheduled_report: {str(e)}")
        raise


def generate_report_file(report_data):
    """
    Generate the actual report file and return file path and size
    """
    try:
        # Import the report generation function
        from django.http import HttpRequest, QueryDict
        from django.contrib.auth.models import AnonymousUser, User
        from .report_views import generate_risk_report
        
        # Create a mock request for report generation
        request = HttpRequest()
        request.method = 'POST'
        
        # Get a superuser for the request
        try:
            superuser = User.objects.filter(is_superuser=True).first()
            request.user = superuser if superuser else AnonymousUser()
        except:
            request.user = AnonymousUser()
        
        # Set request META data to avoid SERVER_NAME error
        request.META = {
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8000',
            'HTTP_HOST': 'localhost:8000',
            'wsgi.url_scheme': 'http',
        }
        
        # Create POST data
        post_data = QueryDict(mutable=True)
        for key, value in report_data.items():
            post_data[key] = str(value)
        request.POST = post_data
        
        # Generate report and get file path
        response = generate_risk_report(request)
        
        if hasattr(response, 'content'):
            # Save the response content to a file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_extension = report_data['reportFormat'].lower()
            if file_extension == 'word':
                file_extension = 'docx'
            elif file_extension == 'excel':
                file_extension = 'xlsx'
            filename = f"scheduled_report_{timestamp}.{file_extension}"
            
            # Create reports directory if it doesn't exist
            reports_dir = os.path.join(settings.MEDIA_ROOT, 'scheduled_reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            file_path = os.path.join(reports_dir, filename)
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(file_path)
            
            return file_path, file_size
        else:
            raise Exception("Report generation failed - no content received")
            
    except Exception as e:
        logger.error(f"Error generating report file: {str(e)}")
        raise





@shared_task(bind=True)
def cleanup_old_report_files(self):
    """
    Clean up old report files (older than 30 days)
    """
    try:
        logger.info("Starting cleanup of old report files")
        
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Find old executions
        old_executions = ScheduledReportExecution.objects.filter(
            completed_at__lt=cutoff_date,
            file_path__isnull=False
        )
        
        deleted_count = 0
        for execution in old_executions:
            try:
                if execution.file_path and os.path.exists(execution.file_path):
                    os.remove(execution.file_path)
                    deleted_count += 1
                    logger.info(f"Deleted old report file: {execution.file_path}")
                
                # Clear file path from execution record
                execution.file_path = ''
                execution.save()
                
            except Exception as e:
                logger.error(f"Error deleting file {execution.file_path}: {str(e)}")
        
        logger.info(f"Cleanup completed. Deleted {deleted_count} old report files")
        return f"Deleted {deleted_count} old report files"
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_report_files: {str(e)}")
        raise


class CallbackTask(Task):
    """Base task class with callback support"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        self.update_job_status(task_id, 'completed', 100, result=retval)
        self.send_completion_notification(task_id, args, kwargs, success=True)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        error_message = str(exc)
        self.update_job_status(task_id, 'failed', 0, error=error_message)
        self.send_completion_notification(task_id, args, kwargs, success=False, error=error_message)
        logger.error(f"Task {task_id} failed: {error_message}")
    
    def update_job_status(self, task_id: str, status: str, progress: int, 
                         result: Any = None, error: str = None):
        """Update job status in cache"""
        try:
            cache_key = f"async_job_{task_id}"
            job_info = cache.get(cache_key, {})
            
            job_info.update({
                'status': status,
                'progress': progress,
                'updated_at': timezone.now().isoformat()
            })
            
            if result is not None:
                job_info['result'] = result
            
            if error is not None:
                job_info['error'] = error
            
            if status == 'completed':
                job_info['completed_at'] = timezone.now().isoformat()
            
            cache.set(cache_key, job_info, timeout=3600)  # 1 hour
            
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
    
    def send_completion_notification(self, task_id: str, args: tuple, kwargs: dict, 
                                   success: bool, error: str = None):
        """Send notification when task completes"""
        try:
            # Get user info from task arguments
            user_id = kwargs.get('user_id') or (args[0] if args else None)
            if not user_id:
                return
            
            user = User.objects.get(id=user_id)
            
            # Send email notification if user has email
            if user.email and kwargs.get('notify_email', False):
                subject = "Report Generation Completed" if success else "Report Generation Failed"
                
                if success:
                    message = f"Your report has been generated successfully. Task ID: {task_id}"
                else:
                    message = f"Report generation failed. Error: {error}. Task ID: {task_id}"
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True
                )
            
            # Update cache notification
            notification_key = f"notification_{user_id}_{task_id}"
            notification_data = {
                'task_id': task_id,
                'success': success,
                'timestamp': timezone.now().isoformat(),
                'message': 'Report generated successfully' if success else f'Report generation failed: {error}'
            }
            
            cache.set(notification_key, notification_data, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")


@shared_task(bind=True, base=CallbackTask)
def generate_report_async(self, user_id: int, config_data: Dict[str, Any], 
                         notify_email: bool = False, priority: str = "normal"):
    """
    Asynchronously generate a risk report
    
    Args:
        user_id: ID of the user requesting the report
        config_data: Report configuration parameters
        notify_email: Whether to send email notification
        priority: Task priority (low, normal, high)
    """
    
    task_id = self.request.id
    logger.info(f"Starting async report generation: {task_id} for user {user_id}")
    
    try:
        # Initialize progress tracking
        self.update_job_status(task_id, 'processing', 5)
        
        # Get user
        user = User.objects.get(id=user_id)
        
        # Activate language
        language = config_data.get('language', 'en')
        activate(language)
        
        # Create report configuration
        self.update_job_status(task_id, 'processing', 10)
        
        config = ReportConfig(
            user=user,
            report_type=config_data.get('reportType', 'full'),
            format=config_data.get('format', 'pdf'),
            language=language,
            company_id=config_data.get('company_id'),
            notes=config_data.get('notes', ''),
            date_range=_parse_date_range(config_data),
            include_assets=config_data.get('include_assets', True),
            include_vulnerabilities=config_data.get('include_vulnerabilities', True),
            include_treatments=config_data.get('include_treatments', True),
            include_statistics=config_data.get('include_statistics', True),
            enable_caching=True
        )
        
        # Generate report data
        self.update_job_status(task_id, 'processing', 30)
        
        with monitor_operation("async_data_generation", "async_report"):
            data_service = OptimizedReportDataService(config)
            report_data = data_service.get_optimized_report_data()
        
        add_metric("async_report_data_generated", 1, "count", "async_report")
        
        # Update progress
        self.update_job_status(task_id, 'processing', 70)
        
        # Generate report file
        with monitor_operation("async_file_generation", "async_report"):
            response = generate_report_file(
                report_data,
                config.report_type,
                config.format
            )
        
        # Save report file (in real implementation, save to file system or cloud storage)
        file_path = _save_report_file(task_id, response, config)
        
        # Update progress
        self.update_job_status(task_id, 'processing', 90)
        
        # Prepare result
        result = {
            'task_id': task_id,
            'file_path': file_path,
            'report_type': config.report_type,
            'format': config.format,
            'generated_at': timezone.now().isoformat(),
            'user_id': user_id,
            'file_size': len(response.content) if hasattr(response, 'content') else 0
        }
        
        add_metric("async_report_completed", 1, "count", "async_report")
        logger.info(f"Async report generation completed: {task_id}")
        
        return result
        
    except Exception as e:
        error_message = f"Error generating async report: {str(e)}"
        logger.error(f"Task {task_id} failed: {error_message}", exc_info=True)
        add_metric("async_report_failed", 1, "count", "async_report")
        raise


@shared_task(bind=True, base=CallbackTask)
def generate_scheduled_report(self, scheduled_report_id: int):
    """
    Generate a scheduled report
    
    Args:
        scheduled_report_id: ID of the scheduled report
    """
    
    task_id = self.request.id
    logger.info(f"Starting scheduled report generation: {task_id} for report {scheduled_report_id}")
    
    try:
        # Get scheduled report
        scheduled_report = ScheduledReport.objects.get(id=scheduled_report_id)
        
        # Create execution record
        execution = ScheduledReportExecution.objects.create(
            scheduled_report=scheduled_report,
            status='running'
        )
        
        # Update progress
        self.update_job_status(task_id, 'processing', 10)
        
        # Prepare configuration
        config_data = {
            'reportType': scheduled_report.report_type,
            'format': scheduled_report.format,
            'language': scheduled_report.language,
            'company_id': scheduled_report.company_id,
            'include_assets': True,
            'include_vulnerabilities': True,
            'include_treatments': True,
            'include_statistics': True,
        }
        
        # Generate report
        result = generate_report_async.apply(
            args=[scheduled_report.user.id, config_data],
            kwargs={'notify_email': scheduled_report.email_notifications, 'priority': 'low'}
        ).get()
        
        # Update execution record
        execution.status = 'completed'
        execution.completed_at = timezone.now()
        execution.file_path = result.get('file_path')
        execution.save()
        
        # Update next execution time
        scheduled_report.update_next_execution()
        
        logger.info(f"Scheduled report generation completed: {task_id}")
        return result
        
    except Exception as e:
        # Update execution record
        if 'execution' in locals():
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()
        
        error_message = f"Error generating scheduled report: {str(e)}"
        logger.error(f"Scheduled task {task_id} failed: {error_message}", exc_info=True)
        raise


@shared_task(bind=True)
def cleanup_old_reports(self, days_to_keep: int = 30):
    """
    Clean up old report files and cache entries
    
    Args:
        days_to_keep: Number of days to keep reports
    """
    
    task_id = self.request.id
    logger.info(f"Starting cleanup task: {task_id}")
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Clean up cache entries
        cache_service = get_cache_service()
        
        # This is a simplified cleanup - in real implementation,
        # you'd iterate through cache keys and remove old ones
        cache_service.clear_expired()
        
        # Clean up old execution records
        from .models import ScheduledReportExecution
        
        old_executions = ScheduledReportExecution.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = old_executions.count()
        old_executions.delete()
        
        logger.info(f"Cleanup completed: removed {count} old execution records")
        
        return {
            'cleaned_executions': count,
            'cleanup_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}", exc_info=True)
        raise


@shared_task(bind=True)
def warm_cache(self, user_id: int, config_list: list):
    """
    Pre-warm cache with common report configurations
    
    Args:
        user_id: User ID to warm cache for
        config_list: List of report configurations to pre-generate
    """
    
    task_id = self.request.id
    logger.info(f"Starting cache warm-up: {task_id} for user {user_id}")
    
    try:
        user = User.objects.get(id=user_id)
        warmed_count = 0
        
        for config_data in config_list:
            try:
                # Generate report data (will be cached)
                config = ReportConfig(
                    user=user,
                    report_type=config_data.get('reportType', 'summary'),
                    format=config_data.get('format', 'pdf'),
                    language=config_data.get('language', 'en'),
                    company_id=config_data.get('company_id'),
                    date_range=_parse_date_range(config_data),
                    include_assets=True,
                    include_vulnerabilities=True,
                    include_treatments=True,
                    include_statistics=True,
                    enable_caching=True
                )
                
                data_service = OptimizedReportDataService(config)
                data_service.get_optimized_report_data()
                
                warmed_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to warm cache for config {config_data}: {e}")
        
        logger.info(f"Cache warm-up completed: {warmed_count} configurations")
        
        return {
            'warmed_count': warmed_count,
            'total_configs': len(config_list)
        }
        
    except Exception as e:
        logger.error(f"Cache warm-up task failed: {str(e)}", exc_info=True)
        raise


def _parse_date_range(config_data: Dict[str, Any]) -> tuple:
    """Parse date range from configuration data"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365)
    
    if config_data.get('startDate'):
        start_date = datetime.strptime(config_data['startDate'], '%Y-%m-%d').date()
    if config_data.get('endDate'):
        end_date = datetime.strptime(config_data['endDate'], '%Y-%m-%d').date()
    
    return (start_date, end_date)


def _save_report_file(task_id: str, response, config: ReportConfig) -> str:
    """
    Save report file to storage
    
    Args:
        task_id: Task ID for unique filename
        response: Django HTTP response with file content
        config: Report configuration
    
    Returns:
        File path where report was saved
    """
    
    import os
    from django.conf import settings
    
    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'async')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate filename
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    extension = _get_file_extension(config.format)
    filename = f"report_{task_id}_{timestamp}.{extension}"
    
    file_path = os.path.join(reports_dir, filename)
    
    # Save file
    with open(file_path, 'wb') as f:
        if hasattr(response, 'content'):
            f.write(response.content)
        else:
            f.write(response.getvalue())
    
    return file_path


def _get_file_extension(format_type: str) -> str:
    """Get file extension for format type"""
    extensions = {
        'pdf': 'pdf',
        'excel': 'xlsx',
        'word': 'docx',
        'html': 'html'
    }
    return extensions.get(format_type, 'pdf')


# Helper functions for Django views
def submit_async_report_task(user_id: int, config_data: Dict[str, Any], 
                           notify_email: bool = False, priority: str = "normal") -> str:
    """
    Submit async report generation task
    
    Returns:
        Task ID
    """
    
    # Choose queue based on priority
    queue_map = {
        'low': 'reports',
        'normal': 'reports', 
        'high': 'reports'
    }
    
    queue = queue_map.get(priority, 'reports')
    
    # Submit task
    result = generate_report_async.apply_async(
        args=[user_id, config_data],
        kwargs={'notify_email': notify_email, 'priority': priority},
        queue=queue
    )
    
    # Store initial job info in cache
    job_info = {
        'id': result.id,
        'status': 'pending',
        'progress': 0,
        'created_at': timezone.now().isoformat(),
        'user_id': user_id,
        'params': config_data,
        'priority': priority
    }
    
    cache_key = f"async_job_{result.id}"
    cache.set(cache_key, job_info, timeout=3600)
    
    return result.id


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status from cache"""
    cache_key = f"async_job_{task_id}"
    return cache.get(cache_key)


def cancel_task(task_id: str) -> bool:
    """Cancel running task"""
    try:
        from celery import current_app
        current_app.control.revoke(task_id, terminate=True)
        
        # Update status in cache
        cache_key = f"async_job_{task_id}"
        job_info = cache.get(cache_key, {})
        job_info.update({
            'status': 'cancelled',
            'cancelled_at': timezone.now().isoformat()
        })
        cache.set(cache_key, job_info, timeout=3600)
        
        return True
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        return False 