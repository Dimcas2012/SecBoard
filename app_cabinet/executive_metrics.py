#  app_cabinet/executive_metrics.py
#  Aggregates metrics for Executive View widgets. Used by executive_view and executive_view_metrics_api.

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, Avg

logger = logging.getLogger(__name__)


def _companies_q(company_ids):
    """Q filter for company if company_ids is non-empty; else no filter (all)."""
    if not company_ids:
        return Q()
    return Q(company_id__in=company_ids)


def get_incidents_critical_mttr(company_ids):
    """Open critical incidents count and MTTR (week/month)."""
    try:
        from app_incident.models import Incident
        from app_incident.models import Currentstate
        qs = Incident.objects.filter(_companies_q(company_ids))
        open_state_ids = list(Currentstate.objects.filter(code__in=('open', 'in-progress', 'in_progress')).values_list('id', flat=True))
        if open_state_ids:
            open_qs = qs.filter(current_state_id__in=open_state_ids)
        else:
            open_qs = qs.filter(current_state__isnull=True)
        critical = open_qs.filter(classification__code__icontains='critical').count() if hasattr(Incident, 'classification') else open_qs.count()
        now = timezone.now()
        month_ago = now - timedelta(days=30)
        closed = qs.filter(updated_at__gte=month_ago)
        closed = closed.filter(current_state__code__in=('closed', 'resolved'))
        mttr_hours = None
        if closed.exists():
            total_sec = 0
            n = 0
            for inc in closed.values_list('occurrence_datetime', 'updated_at')[:500]:
                occ, upd = inc[0], inc[1]
                if occ and upd:
                    total_sec += (upd - occ).total_seconds()
                    n += 1
            if n:
                mttr_hours = total_sec / n / 3600
        return {
            'open_critical': critical,
            'mttr_hours': round(mttr_hours, 1) if mttr_hours is not None else None,
            'period': '30d',
        }
    except Exception as e:
        logger.warning("executive_metrics get_incidents_critical_mttr: %s", e)
        return {'open_critical': 0, 'mttr_hours': None, 'error': str(e)}


def get_mandatory_processes_pct(company_ids):
    """% of mandatory processes completed on time."""
    try:
        from app_compliance.models import MandatoryProcess
        qs = MandatoryProcess.objects.filter(is_active=True)
        if company_ids:
            qs = qs.filter(Q(company_id__in=company_ids) | Q(company__isnull=True))
        total = qs.count()
        if total == 0:
            return {'pct': 100, 'completed': 0, 'total': 0, 'overdue': 0}
        today = timezone.now().date()
        completed_on_time = qs.filter(next_due_date__gte=today, last_completed_date__isnull=False).count()
        completed_late = qs.filter(next_due_date__lt=today, last_completed_date__isnull=False).count()
        overdue = qs.filter(next_due_date__lt=today, last_completed_date__isnull=True).count()
        completed = completed_on_time + completed_late
        pct = round((completed_on_time / total) * 100, 1) if total else 100
        return {'pct': pct, 'completed': completed, 'total': total, 'overdue': overdue}
    except Exception as e:
        logger.warning("executive_metrics get_mandatory_processes_pct: %s", e)
        return {'pct': 0, 'total': 0, 'error': str(e)}


def get_compliance_traffic_light(company_ids):
    """Compliance status per framework (PCI, ISO, GDPR, Local, Internal) - simplified."""
    try:
        from app_compliance.models import ComplianceFramework, Control
        frameworks = ComplianceFramework.objects.filter(status='active')
        if company_ids:
            frameworks = frameworks.filter(Q(company_id__in=company_ids) | Q(company__isnull=True))
        result = []
        for fw in frameworks[:10]:
            controls = Control.objects.filter(category__framework=fw)
            total = controls.count()
            if total == 0:
                result.append({'name': fw.name, 'pct': 0, 'status': 'grey'})
                continue
            completed = controls.filter(status='completed').count()
            pct = round((completed / total) * 100, 1)
            if pct >= 90:
                status = 'green'
            elif pct >= 70:
                status = 'yellow'
            else:
                status = 'red'
            result.append({'name': fw.name, 'pct': pct, 'status': status, 'completed': completed, 'total': total})
        return {'frameworks': result}
    except Exception as e:
        logger.warning("executive_metrics get_compliance_traffic_light: %s", e)
        return {'frameworks': [], 'error': str(e)}


def get_security_index(company_ids):
    """Placeholder aggregate score (can combine risks, incidents, compliance)."""
    try:
        from app_incident.models import Incident
        from app_compliance.models import MandatoryProcess
        inc = Incident.objects.filter(_companies_q(company_ids)).count()
        mp = MandatoryProcess.objects.filter(is_active=True)
        if company_ids:
            mp = mp.filter(Q(company_id__in=company_ids) | Q(company__isnull=True))
        total_mp = mp.count()
        overdue_mp = mp.filter(next_due_date__lt=timezone.now().date(), last_completed_date__isnull=True).count() if total_mp else 0
        score = max(0, 100 - inc * 2 - overdue_mp * 5)
        return {'score': min(100, score), 'label': 'Index'}
    except Exception as e:
        logger.warning("executive_metrics get_security_index: %s", e)
        return {'score': 0, 'error': str(e)}


def get_framework_pct(company_ids):
    """% completed controls per framework."""
    return get_compliance_traffic_light(company_ids)


def get_failed_controls(company_ids):
    """Failed/overdue controls count per framework."""
    try:
        from app_compliance.models import ComplianceFramework, Control
        frameworks = ComplianceFramework.objects.filter(status='active')
        if company_ids:
            frameworks = frameworks.filter(Q(company_id__in=company_ids) | Q(company__isnull=True))
        result = []
        for fw in frameworks[:10]:
            failed = Control.objects.filter(category__framework=fw).exclude(status__in=('completed', 'not_applicable')).count()
            result.append({'name': fw.name, 'failed': failed})
        return {'frameworks': result}
    except Exception as e:
        logger.warning("executive_metrics get_failed_controls: %s", e)
        return {'frameworks': []}


def get_audit_readiness(company_ids):
    """% controls with attached evidence."""
    try:
        from app_compliance.models import Control
        controls = Control.objects.all()
        if company_ids:
            controls = controls.filter(category__framework__company_id__in=company_ids)
        total = controls.count()
        if total == 0:
            return {'pct': 100, 'with_evidence': 0, 'total': 0}
        evidence_rel = getattr(Control, 'evidences', None) or getattr(Control, 'evidence_set', None)
        if evidence_rel:
            with_ev = controls.filter(evidences__isnull=False).distinct().count() if hasattr(Control, 'evidences') else controls.exclude(evidences__isnull=True).distinct().count()
        else:
            with_ev = 0
        pct = round((with_ev / total) * 100, 1) if total else 0
        return {'pct': pct, 'with_evidence': with_ev, 'total': total}
    except Exception as e:
        logger.warning("executive_metrics get_audit_readiness: %s", e)
        return {'pct': 0}


def get_mandatory_status(company_ids):
    """Planned vs completed vs overdue for mandatory processes."""
    try:
        from app_compliance.models import MandatoryProcess
        qs = MandatoryProcess.objects.filter(is_active=True)
        if company_ids:
            qs = qs.filter(Q(company_id__in=company_ids) | Q(company__isnull=True))
        today = timezone.now().date()
        planned = qs.filter(next_due_date__gte=today).count()
        completed = qs.filter(last_completed_date__isnull=False).count()
        overdue = qs.filter(next_due_date__lt=today, last_completed_date__isnull=True).count()
        return {'planned': planned, 'completed': completed, 'overdue': overdue, 'total': qs.count()}
    except Exception as e:
        logger.warning("executive_metrics get_mandatory_status: %s", e)
        return {'planned': 0, 'completed': 0, 'overdue': 0}


def get_risks_by_level(company_ids):
    """Risks count by level (High/Medium/Low)."""
    try:
        from app_risk.models import RiskTreatment, RiskLevel
        qs = RiskTreatment.objects.all()
        if company_ids:
            qs = qs.filter(asset__company_id__in=company_ids)
        by_level = {}
        for rl in RiskLevel.objects.all()[:10]:
            by_level[rl.get_name() or rl.code or str(rl.id)] = qs.filter(highest_risk_level=rl).count()
        return {'by_level': by_level, 'total': qs.count()}
    except Exception as e:
        logger.warning("executive_metrics get_risks_by_level: %s", e)
        return {'by_level': {}, 'total': 0}


def get_top_risks(company_ids):
    """Top 10 risks by residual risk."""
    try:
        from app_risk.models import RiskTreatment
        qs = RiskTreatment.objects.select_related('asset', 'residual_risk_level', 'responsible').filter(residual_risk_level__isnull=False)
        if company_ids:
            qs = qs.filter(asset__company_id__in=company_ids)
        top = list(qs.order_by('-residual_risk_level')[:10].values('id', 'responsible', 'asset__name'))
        return {'items': top[:10]}
    except Exception as e:
        logger.warning("executive_metrics get_top_risks: %s", e)
        return {'items': []}


def get_risk_plans(company_ids):
    """% risks with treatment plans and % closed on time."""
    try:
        from app_risk.models import RiskTreatment, Treatment_status
        qs = RiskTreatment.objects.all()
        if company_ids:
            qs = qs.filter(asset__company_id__in=company_ids)
        total = qs.count()
        with_plan = qs.exclude(description__isnull=True).exclude(description='').count()
        closed_ok = 0
        try:
            closed_status = Treatment_status.objects.filter(code__icontains='close').first()
            if closed_status:
                closed_ok = qs.filter(status=closed_status).count()
        except Exception:
            pass
        pct_plan = round((with_plan / total) * 100, 1) if total else 0
        pct_closed = round((closed_ok / total) * 100, 1) if total else 0
        return {'pct_with_plan': pct_plan, 'pct_closed': pct_closed, 'total': total}
    except Exception as e:
        logger.warning("executive_metrics get_risk_plans: %s", e)
        return {'pct_with_plan': 0, 'pct_closed': 0}


def get_tprm_suppliers(company_ids):
    """TPRM: vendors by risk level."""
    try:
        from app_tprm.models import Vendor
        qs = Vendor.objects.all()
        if company_ids:
            qs = qs.filter(company_id__in=company_ids)
        total = qs.count()
        high = qs.filter(risk_level__in=('high', 'critical')).count()
        return {'total': total, 'high_risk': high}
    except Exception as e:
        logger.warning("executive_metrics get_tprm_suppliers: %s", e)
        return {'total': 0, 'high_risk': 0}


def get_incidents_by_period(company_ids):
    """Incidents per period by severity."""
    try:
        from app_incident.models import Incident
        now = timezone.now()
        week = now - timedelta(days=7)
        month = now - timedelta(days=30)
        qs = Incident.objects.filter(_companies_q(company_ids))
        week_count = qs.filter(occurrence_datetime__gte=week).count()
        month_count = qs.filter(occurrence_datetime__gte=month).count()
        return {'week': week_count, 'month': month_count}
    except Exception as e:
        logger.warning("executive_metrics get_incidents_by_period: %s", e)
        return {'week': 0, 'month': 0}


def get_mttd_mttr(company_ids):
    """MTTD/MTTR for critical incidents - simplified."""
    return get_incidents_critical_mttr(company_ids)


def get_incident_categories(company_ids):
    """Incidents by category (type/classification)."""
    try:
        from app_incident.models import Incident
        qs = Incident.objects.filter(_companies_q(company_ids)).values('incident_type__name', 'classification__name').annotate(c=Count('id'))
        return {'categories': list(qs)}
    except Exception as e:
        logger.warning("executive_metrics get_incident_categories: %s", e)
        return {'categories': []}


def get_fim_critical(company_ids):
    """FIM: open critical changes (WazuhFIMAlert, level=2 Critical)."""
    try:
        from app_soc.models import WazuhFIMAlert
        qs = WazuhFIMAlert.objects.filter(level__lte=2).exclude(processing_status__in=('resolved', 'false_positive'))
        if company_ids:
            qs = qs.filter(client__company_id__in=company_ids)
        return {'open_critical': qs.count()}
    except Exception as e:
        logger.warning("executive_metrics get_fim_critical: %s", e)
        return {'open_critical': 0}


def get_access_requests(company_ids):
    """Open access requests and average approval time."""
    try:
        from app_access.models import AccessRequest
        qs = AccessRequest.objects.filter(status='pending')
        if company_ids:
            qs = qs.filter(company_id__in=company_ids)
        return {'open': qs.count()}
    except Exception as e:
        logger.warning("executive_metrics get_access_requests: %s", e)
        return {'open': 0}


# Threshold: users with admin (or similar) role in more than N systems are "excessive"
EXCESSIVE_RIGHTS_SYSTEMS_THRESHOLD = 3


def get_excessive_rights(company_ids):
    """% users with excessive rights (e.g. admin in >N systems). Based on SystemAccess + AccessRoles."""
    try:
        from django.contrib.auth import get_user_model
        from app_access.models import SystemAccess
        User = get_user_model()
        base = SystemAccess.objects.filter(is_active=True)
        if company_ids:
            base = base.filter(asset__company_id__in=company_ids)
        # Accesses where user has an "admin"-like role (by role name or code)
        admin_accesses = base.filter(
            Q(roles__name__icontains='admin') | Q(roles__code__icontains='admin')
        ).distinct()
        # Total distinct users with any active access (for denominator)
        total_users = User.objects.filter(system_access_granted__in=base).distinct().count()
        if total_users == 0:
            return {'pct': 0, 'excessive_count': 0, 'total_users': 0}
        # Users who have admin-like access in more than N distinct systems
        excessive_users = (
            User.objects.filter(system_access_granted__in=admin_accesses)
            .annotate(num_systems=Count('system_access_granted__asset', distinct=True))
            .filter(num_systems__gt=EXCESSIVE_RIGHTS_SYSTEMS_THRESHOLD)
        )
        excessive_count = excessive_users.count()
        pct = round((excessive_count / total_users) * 100, 1)
        return {
            'pct': pct,
            'excessive_count': excessive_count,
            'total_users': total_users,
            'threshold': EXCESSIVE_RIGHTS_SYSTEMS_THRESHOLD,
        }
    except Exception as e:
        logger.warning("executive_metrics get_excessive_rights: %s", e)
        return {'pct': 0, 'excessive_count': 0, 'total_users': 0, 'error': str(e)}


def get_access_review(company_ids):
    """Status of periodic access reviews: total, overdue (never or >90 days), on time."""
    try:
        from app_access.models import SystemAccess
        review_days = 90
        threshold = timezone.now() - timedelta(days=review_days)
        qs = SystemAccess.objects.filter(is_active=True)
        if company_ids:
            qs = qs.filter(asset__company_id__in=company_ids)
        total = qs.count()
        if total == 0:
            return {'total': 0, 'overdue': 0, 'on_time': 0, 'pct_reviewed': 100, 'status': 'N/A'}
        overdue = qs.filter(Q(last_review__isnull=True) | Q(last_review__lt=threshold)).count()
        on_time = total - overdue
        pct_reviewed = round((on_time / total) * 100, 1) if total else 100
        if pct_reviewed >= 90:
            status = 'OK'
        elif pct_reviewed >= 70:
            status = 'attention'
        else:
            status = 'overdue'
        return {
            'total': total,
            'overdue': overdue,
            'on_time': on_time,
            'pct_reviewed': pct_reviewed,
            'status': status,
        }
    except Exception as e:
        logger.warning("executive_metrics get_access_review: %s", e)
        return {'total': 0, 'overdue': 0, 'status': 'N/A', 'error': str(e)}


def get_api_keys(company_ids):
    """API keys: active, unused, without owner."""
    try:
        from app_keycert.models import KeyCertificates
        qs = KeyCertificates.objects.all()
        if company_ids:
            qs = qs.filter(company_id__in=company_ids)
        total = qs.count()
        no_owner = qs.filter(owner_cabinet_user__isnull=True, owner__isnull=True).count()
        return {'total': total, 'without_owner': no_owner}
    except Exception as e:
        logger.warning("executive_metrics get_api_keys: %s", e)
        return {'total': 0, 'without_owner': 0}


def get_training_completion(company_ids):
    """% staff completed mandatory training - stub."""
    try:
        from app_study.models import QuizAttempt, Quiz
        passed = QuizAttempt.objects.filter(completed=True).count()
        total_quizzes = Quiz.objects.count()
        return {'pct': round((passed / total_quizzes) * 100, 1) if total_quizzes else 0}
    except Exception as e:
        logger.warning("executive_metrics get_training_completion: %s", e)
        return {'pct': 0}


def get_quiz_results(company_ids):
    """Average quiz scores - stub."""
    try:
        from app_study.models import QuizAttempt
        from django.db.models import Avg
        r = QuizAttempt.objects.filter(completed=True).aggregate(avg=Avg('score'))
        return {'avg_score': round(r['avg'] or 0, 1)}
    except Exception as e:
        logger.warning("executive_metrics get_quiz_results: %s", e)
        return {'avg_score': 0}


def get_gophish_metrics(company_ids):
    """Gophish: open/click rates - stub."""
    try:
        from app_gophish.models import Campaign
        total = Campaign.objects.count()
        return {'campaigns': total}
    except Exception as e:
        logger.warning("executive_metrics get_gophish_metrics: %s", e)
        return {'campaigns': 0}


def get_department_risk_profile(company_ids):
    """Department risk map: risk level + awareness per department (org structure + risks + training)."""
    try:
        from app_cabinet.models import Department
        from app_risk.models import RiskTreatment
        from app_study.models import QuizAttempt
        from django.db.models import F
        departments_qs = Department.objects.all()
        if company_ids:
            departments_qs = departments_qs.filter(company_id__in=company_ids)
        departments_qs = departments_qs.order_by('name')
        high_critical_codes = ['high', 'critical']
        result = []
        for dept in departments_qs:
            # Risk: RiskTreatment for assets owned by this department (asset.owners.cabinet_user.department)
            risk_qs = RiskTreatment.objects.filter(
                asset__owners__cabinet_user__department_id=dept.id
            ).distinct()
            risk_total = risk_qs.count()
            risk_high = risk_qs.filter(
                highest_risk_level__code__in=high_critical_codes
            ).distinct().count() if risk_total else 0
            # Derive risk level label
            if risk_high > 0:
                risk_label = 'high'
            elif risk_total > 0:
                risk_label = 'medium'
            else:
                risk_label = 'low'
            # Awareness: % of users in this department who passed at least one quiz
            user_ids_in_dept = [
                u for u in Department.objects.filter(pk=dept.id).values_list(
                    'cabinetuser__user_id', flat=True
                ).distinct() if u is not None
            ]
            total_users = len(user_ids_in_dept)
            if total_users == 0:
                awareness_pct = None
            else:
                passed_user_ids = set(
                    QuizAttempt.objects.filter(
                        completed=True,
                        user_id__in=user_ids_in_dept,
                    ).filter(score__gte=F('quiz__passing_score')).values_list(
                        'user_id', flat=True
                    ).distinct()
                )
                awareness_pct = round((len(passed_user_ids) / total_users) * 100, 1)
            result.append({
                'id': dept.id,
                'name': dept.name or '',
                'risk_total': risk_total,
                'risk_high': risk_high,
                'risk_label': risk_label,
                'awareness_pct': awareness_pct,
                'total_users': total_users,
            })
        return {'departments': result}
    except Exception as e:
        logger.warning("executive_metrics get_department_risk_profile: %s", e)
        return {'departments': [], 'error': str(e)}


# Map widget_id -> handler function
WIDGET_HANDLERS = {
    'security_index': get_security_index,
    'incidents_critical_mttr': get_incidents_critical_mttr,
    'mandatory_processes_pct': get_mandatory_processes_pct,
    'compliance_traffic_light': get_compliance_traffic_light,
    'framework_pct': get_framework_pct,
    'failed_controls': get_failed_controls,
    'audit_readiness': get_audit_readiness,
    'mandatory_status': get_mandatory_status,
    'risks_by_level': get_risks_by_level,
    'top_risks': get_top_risks,
    'risk_plans': get_risk_plans,
    'tprm_suppliers': get_tprm_suppliers,
    'incidents_by_period': get_incidents_by_period,
    'mttd_mttr': get_mttd_mttr,
    'incident_categories': get_incident_categories,
    'fim_critical': get_fim_critical,
    'access_requests': get_access_requests,
    'excessive_rights': get_excessive_rights,
    'access_review': get_access_review,
    'api_keys': get_api_keys,
    'training_completion': get_training_completion,
    'quiz_results': get_quiz_results,
    'gophish_metrics': get_gophish_metrics,
    'department_risk_profile': get_department_risk_profile,
}


def get_executive_metrics(company_ids, widget_ids):
    """
    Return dict of widget_id -> metric data for requested widget_ids.
    company_ids: list of company PKs to filter (empty = all companies the user can see - caller must filter).
    """
    result = {}
    for wid in widget_ids:
        if wid not in WIDGET_HANDLERS:
            result[wid] = {'error': 'unknown_widget'}
            continue
        try:
            result[wid] = WIDGET_HANDLERS[wid](company_ids)
        except Exception as e:
            logger.exception("executive_metrics %s", wid)
            result[wid] = {'error': str(e)}
    return result
