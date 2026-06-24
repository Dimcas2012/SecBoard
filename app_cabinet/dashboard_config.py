#  app_cabinet/dashboard_config.py
#  Section and widget definitions for Executive View (Platform Role dashboard).
#  Used by PlatformRoleDashboardConfig and executive_view.

from django.utils.translation import gettext_lazy as _

# Section IDs and widget IDs must match these definitions when saving/loading config.

EXECUTIVE_SECTIONS = [
    {
        'id': 'top_panel',
        'label': _('Overall security state (Top panel)'),
        'description': _('At-a-glance security status.'),
        'widgets': [
            {'id': 'security_index', 'label': _('Organization security index (aggregate scoring)')},
            {'id': 'incidents_critical_mttr', 'label': _('Open critical incidents / MTTR (week/month)')},
            {'id': 'mandatory_processes_pct', 'label': _('% mandatory processes completed on time')},
            {'id': 'compliance_traffic_light', 'label': _('Compliance status (PCI DSS, ISO 27002, GDPR, Local, Internal)')},
        ],
    },
    {
        'id': 'compliance',
        'label': _('Compliance and audits'),
        'description': _('Data from GDPR, Frameworks, Local, Internal, Mandatory processes, PCI DSS, ISO 27002.'),
        'widgets': [
            {'id': 'framework_pct', 'label': _('%s completed controls per framework') % '%'},
            {'id': 'failed_controls', 'label': _('Failed/overdue controls and action items per framework')},
            {'id': 'audit_readiness', 'label': _('Audit readiness (%s controls with attached evidence)') % '%'},
            {'id': 'mandatory_status', 'label': _('Mandatory processes: planned vs completed vs overdue')},
        ],
    },
    {
        'id': 'risks_tprm',
        'label': _('Risks and TPRM'),
        'description': _('Data from Risk assessment, Risk report, TPRM.'),
        'widgets': [
            {'id': 'risks_by_level', 'label': _('Risks count by level (High/Medium/Low) and trend')},
            {'id': 'top_risks', 'label': _('Top 10 risks by residual risk (owner/department)')},
            {'id': 'risk_plans', 'label': _('%s risks with approved treatment plans and %s closed on time') % ('%', '%')},
            {'id': 'tprm_suppliers', 'label': _('TPRM: suppliers by risk level, %s overdue assessments, high-risk without controls') % '%'},
        ],
    },
    {
        'id': 'operations',
        'label': _('Operational security (SOC / incidents)'),
        'description': _('Data from Incident register, FIM Dashboard.'),
        'widgets': [
            {'id': 'incidents_by_period', 'label': _('Incidents per period (week/month/quarter) by severity + trend')},
            {'id': 'mttd_mttr', 'label': _('MTTD and MTTR for critical incidents')},
            {'id': 'incident_categories', 'label': _('Incidents by category (access/human/technical)')},
            {'id': 'fim_critical', 'label': _('FIM: open critical integrity changes, top systems, noise vs relevant')},
        ],
    },
    {
        'id': 'access',
        'label': _('Access and identities'),
        'description': _('Data from Access records, Access matrix, My requests, Manage requests, API management.'),
        'widgets': [
            {'id': 'access_requests', 'label': _('Open access requests and average approval time (by system criticality)')},
            {'id': 'excessive_rights', 'label': _('%s users with excessive rights (e.g. admin in >N systems)') % '%'},
            {'id': 'access_review', 'label': _('Status of periodic access reviews')},
            {'id': 'api_keys', 'label': _('API keys: active, unused >X days, service accounts without owner')},
        ],
    },
    {
        'id': 'people',
        'label': _('Organization, people, awareness'),
        'description': _('Data from Org chart, Org structure, Users/groups, Training, Gophish, Quiz results.'),
        'widgets': [
            {'id': 'training_completion', 'label': _('%s staff completed mandatory security training (by department)') % '%'},
            {'id': 'quiz_results', 'label': _('Average quiz scores and gap areas by topic')},
            {'id': 'gophish_metrics', 'label': _('Gophish: open/click/data-entry rates and trends')},
            {'id': 'department_risk_profile', 'label': _('Department risk map (risk level + awareness)')},
        ],
    },
]


def get_default_config():
    """Return default config: all sections enabled with all widgets."""
    return {
        'sections': [
            {
                'id': s['id'],
                'enabled': True,
                'widgets': [w['id'] for w in s['widgets']],
            }
            for s in EXECUTIVE_SECTIONS
        ],
    }


def get_section_by_id(section_id):
    for s in EXECUTIVE_SECTIONS:
        if s['id'] == section_id:
            return s
    return None


def get_widget_label(section_id, widget_id):
    section = get_section_by_id(section_id)
    if not section:
        return widget_id
    for w in section['widgets']:
        if w['id'] == widget_id:
            return w['label']
    return widget_id


def normalize_config(config):
    """Ensure config has correct structure; fill missing sections/widgets from defaults."""
    if not config or not isinstance(config, dict):
        config = {}
    default = get_default_config()
    sections_in = config.get('sections') or []
    section_ids_seen = set()
    sections_out = []
    for def_s in default['sections']:
        sid = def_s['id']
        section_def = get_section_by_id(sid)
        if not section_def:
            continue
        existing = next((s for s in sections_in if isinstance(s, dict) and s.get('id') == sid), None)
        if existing is not None:
            section_ids_seen.add(sid)
            enabled = bool(existing.get('enabled', True))
            widgets_in = existing.get('widgets')
            if not isinstance(widgets_in, list):
                widgets_in = [w['id'] for w in section_def['widgets']]
            valid_widget_ids = {w['id'] for w in section_def['widgets']}
            widgets_out = [w for w in widgets_in if w in valid_widget_ids]
            sections_out.append({'id': sid, 'enabled': enabled, 'widgets': widgets_out})
        else:
            sections_out.append({
                'id': sid,
                'enabled': True,
                'widgets': [w['id'] for w in section_def['widgets']],
            })
    return {'sections': sections_out}
