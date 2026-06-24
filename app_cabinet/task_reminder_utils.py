# SecBoard/app_cabinet/task_reminder_utils.py
"""Build and send cabinet task reminder emails (used from views and Celery)."""
import logging
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def _get_site_base_url():
    """Canonical site origin from Site URL Settings (Site Domain + protocol)."""
    try:
        from app_conf.models import SiteSettings

        site_settings = SiteSettings.get_settings()
        if site_settings and site_settings.site_domain and site_settings.site_domain.strip():
            return site_settings.get_site_url().rstrip('/')
    except Exception:
        logger.debug('Could not load SiteSettings for task reminder URL', exc_info=True)
    return (getattr(settings, 'PUBLIC_BASE_URL', None) or '').rstrip('/')


def estimate_next_periodic_task_run(periodic_task):
    """
    Approximate next run datetime for a django_celery_beat PeriodicTask (crontab only).
    Uses the same remaining_estimate logic as Celery Beat; requires last_run_at for best
    accuracy (Beat sets it after the first tick).
    """
    from django.utils import timezone as dj_tz

    if (
        not periodic_task
        or not periodic_task.enabled
        or not periodic_task.crontab_id
    ):
        return None
    try:
        sched = periodic_task.schedule
        py_tz = getattr(sched, 'tz', None)

        last = periodic_task.last_run_at
        if last is None:
            last = dj_tz.now()
        if dj_tz.is_naive(last):
            last = dj_tz.make_aware(last, dj_tz.get_current_timezone())

        if py_tz is not None:
            last_anchor = last.astimezone(py_tz)
        else:
            last_anchor = last

        rem = sched.remaining_estimate(last_anchor)
        nxt = last_anchor + rem
        if rem.total_seconds() <= 0:
            now_anchor = sched.nowfunc() if hasattr(sched, 'nowfunc') else last_anchor
            rem2 = sched.remaining_estimate(now_anchor)
            nxt = now_anchor + rem2
        return nxt
    except Exception:
        logger.debug('estimate_next_periodic_task_run failed', exc_info=True)
        return None


def build_task_reminder_plain_body(cabinet_user):
    """Plain-text body summarizing open tasks for one cabinet user."""
    from app_cabinet.views import get_tasks_context_for_cabinet_user, get_tasks_count_for_cabinet_user

    user = cabinet_user.user
    name = user.get_full_name() or user.username
    total = get_tasks_count_for_cabinet_user(cabinet_user)
    ctx = get_tasks_context_for_cabinet_user(cabinet_user)
    rm = ctx.get('risk_monitoring_review_tasks') or {}

    base = _get_site_base_url()
    path = reverse('personal_cabinet')
    link = f"{base}{path}" if base else path

    lines = [
        _('Hello %(name)s,') % {'name': name},
        '',
        _('You have %(n)s open task(s) in the SecBoard cabinet.') % {'n': total},
        _('Open your personal cabinet: %(url)s') % {'url': link},
        '',
    ]

    if total == 0:
        lines.append(_('There are no pending tasks in your cabinet at this time.'))
        return '\n'.join(lines)

    lines.append(_('Summary:'))

    def add(label, n):
        if n:
            lines.append(f"  • {label}: {n}")

    add(_('Mandatory processes (overdue)'), len(ctx.get('mandatory_tasks_overdue', [])))
    add(_('Mandatory processes (due within 3 days)'), len(ctx.get('mandatory_tasks_due_3d', [])))
    add(_('Mandatory processes (due within 30 days)'), len(ctx.get('mandatory_tasks_due_30d', [])))
    add(_('Quizzes not passed'), len(ctx.get('tasks_quizzes_not_passed', [])))
    add(_('Keys/certificates (expired)'), len(ctx.get('keycert_tasks_expired', [])))
    add(_('Keys/certificates (expiring within 30 days)'), len(ctx.get('keycert_tasks_expiring_30d', [])))
    add(_('Key/Certificate inventory actualize'), len(ctx.get('keycert_tasks_actualize', [])))
    add(_('Asset tasks'), len(ctx.get('asset_tasks_actualize', [])))
    add(_('TPRM vendor actualize'), len(ctx.get('vendor_tasks_actualize', [])))
    add(_('TPRM vendor contract end (30 days)'), len(ctx.get('vendor_tasks_contract_end', [])))
    add(_('Software tasks'), len(ctx.get('software_tasks_actualize', [])))
    add(_('External media tasks'), len(ctx.get('external_media_tasks_actualize', [])))
    add(_('Access requests to approve'), len(ctx.get('access_requests_tasks_approve', [])))
    add(_('Documents to approve'), len(ctx.get('document_approve_tasks', [])))
    add(_('Familiarization tasks'), len(ctx.get('familiarization_tasks', [])))
    add(_('Framework compliance tasks'), len(ctx.get('framework_compliance_tasks', [])))
    add(_('Local compliance tasks'), len(ctx.get('local_compliance_tasks', [])))
    add(_('Internal compliance tasks'), len(ctx.get('internal_compliance_tasks', [])))
    add(_('Risk treatment tasks'), len(ctx.get('risk_treatment_tasks', [])))
    add(_('Risk monitoring reviews (overdue)'), len(rm.get('overdue', [])))
    add(_('Risk monitoring reviews (due within 7 days)'), len(rm.get('due_7d', [])))
    add(_('Risk monitoring reviews (due within 30 days)'), len(rm.get('due_30d', [])))

    return '\n'.join(lines)


def send_task_reminder_emails_for_user_ids(cabinet_user_ids):
    """
    Send one email per cabinet user. Returns (sent_count, skipped_count, errors list of str).
    Uses CabinetSettings.mail_account.
    """
    from app_cabinet.models import CabinetUser, CabinetSettings
    from app_cabinet.views import send_email

    settings_row = CabinetSettings.objects.first()
    account = settings_row.mail_account if settings_row else None
    if not account:
        return 0, 0, [_('Cabinet mail account is not configured in Cabinet Settings.')]

    qs = CabinetUser.objects.filter(pk__in=cabinet_user_ids).select_related('user')
    sent = 0
    skipped = 0
    errors = []
    subject = _('SecBoard: reminder about your tasks')

    for cu in qs:
        email_addr = (cu.user.email or '').strip()
        if not email_addr:
            skipped += 1
            continue
        try:
            body = build_task_reminder_plain_body(cu)
            ok, msg = send_email(account, email_addr, str(subject), body)
            if ok:
                sent += 1
            else:
                errors.append(f"{email_addr}: {msg}")
        except Exception as ex:
            logger.exception('Task reminder email failed for cabinet user %s', cu.pk)
            errors.append(f"{email_addr}: {ex}")

    return sent, skipped, errors
