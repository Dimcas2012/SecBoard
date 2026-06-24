# SecBoard/app_cabinet/tasks.py
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='app_cabinet.tasks.run_cabinet_task_reminder_schedule')
def run_cabinet_task_reminder_schedule(schedule_id=None, **kwargs):
    """Send task reminder emails to all recipients of a saved schedule."""
    sid = schedule_id if schedule_id is not None else kwargs.get('schedule_id')
    if sid is None:
        logger.warning('run_cabinet_task_reminder_schedule called without schedule_id')
        return

    from app_cabinet.models import CabinetTaskReminderSchedule
    from app_cabinet.task_reminder_utils import send_task_reminder_emails_for_user_ids

    try:
        sch = CabinetTaskReminderSchedule.objects.prefetch_related('recipients').get(
            pk=sid, is_active=True
        )
    except CabinetTaskReminderSchedule.DoesNotExist:
        logger.warning('CabinetTaskReminderSchedule id=%s not found or inactive', sid)
        return

    ids = list(
        sch.recipients.filter(company_id=sch.company_id).values_list('id', flat=True)
    )
    if not ids:
        return

    sent, skipped, errors = send_task_reminder_emails_for_user_ids(ids)
    if errors:
        logger.warning(
            'Task reminder schedule %s: sent=%s skipped=%s errors=%s',
            sid, sent, skipped, errors[:5],
        )
    sch.last_sent_at = timezone.now()
    sch.save(update_fields=['last_sent_at'])
