# SecBoard/app_tprm/signals.py
import logging

from django.db.models.signals import pre_save, post_save, m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext as _

from .models import Vendor, VendorHistory, TprmOwner

logger = logging.getLogger(__name__)

_old_vendor_instances = {}


def _history_user(vendor):
    return getattr(vendor, '_tprm_history_user', None) or getattr(vendor, 'created_by', None)


def _fmt_fk(obj):
    if obj is None:
        return str(_('None'))
    if hasattr(obj, 'get_name'):
        return obj.get_name()
    return str(obj)


_HIST_DISP_MAX = 2000


def _hist_disp_text(val):
    if val is None:
        return ''
    s = str(val).strip()
    if len(s) > _HIST_DISP_MAX:
        return s[:_HIST_DISP_MAX] + '…'
    return s


def _hist_disp_bool(val):
    return str(_('Yes')) if val else str(_('No'))


def _hist_disp_date(d):
    if d is None:
        return str(_('None'))
    return d.strftime('%d.%m.%Y')


def _owners_snapshot_csv(vendor):
    qs = vendor.owners.select_related('cabinet_user__user').all()
    names = sorted(o.name for o in qs if o.name)
    if not names:
        return str(_('None'))
    return ', '.join(names)


@receiver(pre_save, sender=Vendor)
def _vendor_store_old(sender, instance, **kwargs):
    if getattr(instance, '_tprm_skip_history', False):
        return
    if getattr(instance, '_tprm_history_action_override', None):
        # Actualize / mark-not-actual: handled in post_save; avoid storing stale "old" for diff
        return
    if instance.pk:
        try:
            _old_vendor_instances[instance.pk] = Vendor.objects.get(pk=instance.pk)
        except Vendor.DoesNotExist:
            pass


@receiver(post_save, sender=Vendor)
def _vendor_log_save(sender, instance, created, **kwargs):
    if getattr(instance, '_tprm_skip_history', False):
        _old_vendor_instances.pop(instance.pk, None)
        return
    try:
        override = getattr(instance, '_tprm_history_action_override', None)
        if override == VendorHistory.ACTION_ACTUALIZED:
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_ACTUALIZED,
                action_by=_history_user(instance),
                details=_('Vendor record actualized'),
                changes=None,
            )
            _old_vendor_instances.pop(instance.pk, None)
            return
        if override == VendorHistory.ACTION_MARKED_NOT_ACTUAL:
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_MARKED_NOT_ACTUAL,
                action_by=_history_user(instance),
                details=_('Vendor marked as no longer actual'),
                changes={'comment': getattr(instance, 'marked_no_longer_comment', '') or ''},
            )
            _old_vendor_instances.pop(instance.pk, None)
            return

        user = _history_user(instance)

        if created:
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_CREATED,
                action_by=user,
                details=_('Vendor created'),
                changes={
                    'name': instance.name,
                    'company': _fmt_fk(instance.company),
                },
            )
            return

        old = _old_vendor_instances.pop(instance.pk, None)
        if not old:
            return

        field_diffs = []
        field_changes = []

        def _add_diff(field_key, label, cmp_old, cmp_new, disp_old, disp_new):
            if cmp_old != cmp_new:
                field_diffs.append({
                    'field': field_key,
                    'label': str(label),
                    'old': disp_old,
                    'new': disp_new,
                })
                field_changes.append(str(label))

        _add_diff('name', _('Vendor Name'), old.name, instance.name,
                  _hist_disp_text(old.name), _hist_disp_text(instance.name))
        _add_diff('description', _('Description'), old.description, instance.description,
                  _hist_disp_text(old.description), _hist_disp_text(instance.description))
        _add_diff('contract', _('Contract'), old.contract, instance.contract,
                  _hist_disp_text(old.contract), _hist_disp_text(instance.contract))
        _add_diff('contract_validity', _('Contract validity period'),
                  old.contract_validity, instance.contract_validity,
                  _hist_disp_text(old.contract_validity), _hist_disp_text(instance.contract_validity))
        _add_diff('contract_end_date', _('Contract end date'),
                  old.contract_end_date, instance.contract_end_date,
                  _hist_disp_date(old.contract_end_date), _hist_disp_date(instance.contract_end_date))
        _add_diff('website', _('Website'), old.website or '', instance.website or '',
                  _hist_disp_text(old.website or ''), _hist_disp_text(instance.website or ''))
        _add_diff('contact_person', _('Contact Person'), old.contact_person, instance.contact_person,
                  _hist_disp_text(old.contact_person), _hist_disp_text(instance.contact_person))
        _add_diff('contact_email', _('Contact Email'), old.contact_email, instance.contact_email,
                  _hist_disp_text(old.contact_email), _hist_disp_text(instance.contact_email))
        _add_diff('contact_phone', _('Contact Phone'), old.contact_phone, instance.contact_phone,
                  _hist_disp_text(old.contact_phone), _hist_disp_text(instance.contact_phone))
        _add_diff('services_provided', _('Services Provided'),
                  old.services_provided, instance.services_provided,
                  _hist_disp_text(old.services_provided), _hist_disp_text(instance.services_provided))
        _add_diff('nda_in_contract', _('NDA in contract'), old.nda_in_contract, instance.nda_in_contract,
                  _hist_disp_bool(old.nda_in_contract), _hist_disp_bool(instance.nda_in_contract))
        _add_diff('is_active', _('Active'), old.is_active, instance.is_active,
                  _hist_disp_bool(old.is_active), _hist_disp_bool(instance.is_active))
        _add_diff('risk_level', _('Risk Level'), old.risk_level_id, instance.risk_level_id,
                  _fmt_fk(old.risk_level), _fmt_fk(instance.risk_level))
        _add_diff('status', _('Status'), old.status_id, instance.status_id,
                  _fmt_fk(old.status), _fmt_fk(instance.status))
        _add_diff('criticality_level', _('Criticality level'),
                  old.criticality_level_id, instance.criticality_level_id,
                  _fmt_fk(old.criticality_level), _fmt_fk(instance.criticality_level))
        _add_diff('sanctions_verification_status', _('Sanctions verification'),
                  old.sanctions_verification_status_id, instance.sanctions_verification_status_id,
                  _fmt_fk(old.sanctions_verification_status), _fmt_fk(instance.sanctions_verification_status))
        _add_diff('data_access_level', _('Data Access Level'),
                  old.data_access_level_id, instance.data_access_level_id,
                  _fmt_fk(old.data_access_level), _fmt_fk(instance.data_access_level))
        _add_diff('data_access_rights', _('Data Access rights'),
                  old.data_access_rights_id, instance.data_access_rights_id,
                  _fmt_fk(old.data_access_rights), _fmt_fk(instance.data_access_rights))
        _add_diff('company', _('Company'), old.company_id, instance.company_id,
                  _fmt_fk(old.company), _fmt_fk(instance.company))

        if field_changes:
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_MODIFIED,
                action_by=user,
                details=_('Fields changed: {}').format(', '.join(field_changes)),
                changes={
                    'field_diffs': field_diffs,
                    'changed_fields': field_changes,
                },
            )
    except Exception as e:
        logger.exception('Error logging vendor save: %s', e)


@receiver(m2m_changed, sender=Vendor.owners.through)
def _vendor_owners_m2m_changed(sender, instance, action, pk_set, **kwargs):
    if not isinstance(instance, Vendor):
        return
    if getattr(instance, '_tprm_skip_history', False):
        return
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    try:
        user = _history_user(instance)
        if action == 'post_add':
            added = TprmOwner.objects.filter(pk__in=pk_set)
            names = ', '.join(o.name for o in added)
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_OWNERS_CHANGED,
                action_by=user,
                details=_('Owners added: {}').format(names) if names else _('Owners updated'),
                changes={
                    'type': 'add',
                    'items': [{'id': o.pk, 'name': o.name} for o in added],
                    'owners_current': _owners_snapshot_csv(instance),
                },
            )
        elif action == 'post_remove':
            removed = TprmOwner.objects.filter(pk__in=pk_set)
            names = ', '.join(o.name for o in removed)
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_OWNERS_CHANGED,
                action_by=user,
                details=_('Owners removed: {}').format(names) if names else _('Owners updated'),
                changes={
                    'type': 'remove',
                    'items': [{'id': o.pk, 'name': o.name} for o in removed],
                    'owners_current': _owners_snapshot_csv(instance),
                },
            )
        elif action == 'post_clear':
            VendorHistory.objects.create(
                vendor=instance,
                action=VendorHistory.ACTION_OWNERS_CHANGED,
                action_by=user,
                details=_('All owners cleared'),
                changes={
                    'type': 'clear',
                    'owners_current': _owners_snapshot_csv(instance),
                },
            )
    except Exception as e:
        logger.exception('Error logging vendor owners change: %s', e)
