# SecBoard/app_asset/signals.py
from django.db.models.signals import pre_save, post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext as _
from .models import InformationAsset, AssetHistory, AssetOwner, AssetAdministrator
import json
import logging

logger = logging.getLogger(__name__)

# Глобальний словник для зберігання старих значень перед збереженням
_old_instances = {}


@receiver(pre_save, sender=InformationAsset)
def store_old_instance(sender, instance, **kwargs):
    """Зберігаємо старе значення перед збереженням"""
    if instance.pk:
        try:
            _old_instances[instance.pk] = InformationAsset.objects.get(pk=instance.pk)
        except InformationAsset.DoesNotExist:
            pass


@receiver(post_save, sender=InformationAsset)
def log_asset_save(sender, instance, created, **kwargs):
    """Логування створення та зміни активу"""
    try:
        action = AssetHistory.ACTION_CREATED if created else AssetHistory.ACTION_MODIFIED
        details_parts = []
        changes = {}

        if created:
            details_parts.append(_("Asset created"))
            changes = {
                'name': instance.name,
                'company': str(instance.company),
                'group': str(instance.group) if instance.group else None,
                'asset_type': str(instance.asset_type) if instance.asset_type else None,
            }
            AssetHistory.objects.create(
                asset=instance,
                action=action,
                action_by=instance.last_modified_by,
                details=_("Asset created"),
                changes=changes
            )
        else:
            # Відстеження змін полів
            old_instance = _old_instances.get(instance.pk)
            if old_instance:
                # Перевіряємо зміни CIA
                if old_instance.confidentiality_id != instance.confidentiality_id:
                    AssetHistory.objects.create(
                        asset=instance,
                        action=AssetHistory.ACTION_CIA_CONFIDENTIALITY_CHANGED,
                        action_by=instance.last_modified_by,
                        details=_("Confidentiality changed from {} to {}").format(
                            old_instance.confidentiality.get_name() if old_instance.confidentiality else _("None"),
                            instance.confidentiality.get_name() if instance.confidentiality else _("None")
                        ),
                        changes={
                            'field': 'confidentiality',
                            'old_value': old_instance.confidentiality_id,
                            'new_value': instance.confidentiality_id,
                            'old_name': old_instance.confidentiality.get_name() if old_instance.confidentiality else None,
                            'new_name': instance.confidentiality.get_name() if instance.confidentiality else None,
                        }
                    )
                
                if old_instance.integrity_id != instance.integrity_id:
                    AssetHistory.objects.create(
                        asset=instance,
                        action=AssetHistory.ACTION_CIA_INTEGRITY_CHANGED,
                        action_by=instance.last_modified_by,
                        details=_("Integrity changed from {} to {}").format(
                            old_instance.integrity.get_name() if old_instance.integrity else _("None"),
                            instance.integrity.get_name() if instance.integrity else _("None")
                        ),
                        changes={
                            'field': 'integrity',
                            'old_value': old_instance.integrity_id,
                            'new_value': instance.integrity_id,
                            'old_name': old_instance.integrity.get_name() if old_instance.integrity else None,
                            'new_name': instance.integrity.get_name() if instance.integrity else None,
                        }
                    )
                
                if old_instance.availability_id != instance.availability_id:
                    AssetHistory.objects.create(
                        asset=instance,
                        action=AssetHistory.ACTION_CIA_AVAILABILITY_CHANGED,
                        action_by=instance.last_modified_by,
                        details=_("Availability changed from {} to {}").format(
                            old_instance.availability.get_name() if old_instance.availability else _("None"),
                            instance.availability.get_name() if instance.availability else _("None")
                        ),
                        changes={
                            'field': 'availability',
                            'old_value': old_instance.availability_id,
                            'new_value': instance.availability_id,
                            'old_name': old_instance.availability.get_name() if old_instance.availability else None,
                            'new_name': instance.availability.get_name() if instance.availability else None,
                        }
                    )
                
                # Перевіряємо інші зміни полів
                field_changes = []
                if old_instance.name != instance.name:
                    field_changes.append(_("Name"))
                if old_instance.description != instance.description:
                    field_changes.append(_("Description"))
                if old_instance.location != instance.location:
                    field_changes.append(_("Location"))
                if old_instance.group_id != instance.group_id:
                    field_changes.append(_("Group"))
                if old_instance.asset_type_id != instance.asset_type_id:
                    field_changes.append(_("Asset Type"))
                if old_instance.access_manage != instance.access_manage:
                    field_changes.append(_("Access Manage"))
                if getattr(old_instance, "is_active", True) != instance.is_active:
                    field_changes.append(_("Active"))
                
                if field_changes:
                    AssetHistory.objects.create(
                        asset=instance,
                        action=action,
                        action_by=instance.last_modified_by,
                        details=_("Fields changed: {}").format(", ".join(field_changes)),
                        changes={'changed_fields': field_changes}
                    )
                
                # Очищаємо збережене значення
                _old_instances.pop(instance.pk, None)
    except Exception as e:
        logger.error(f"Error logging asset save: {str(e)}")


@receiver(post_delete, sender=InformationAsset)
def log_asset_delete(sender, instance, **kwargs):
    """Логування видалення активу"""
    try:
        AssetHistory.objects.create(
            asset=instance,
            action=AssetHistory.ACTION_DELETED,
            action_by=None,  # Можна передати request.user через kwargs, якщо потрібно
            details=_("Asset deleted: {}").format(instance.name)
        )
    except Exception as e:
        logger.error(f"Error logging asset delete: {str(e)}")


def log_m2m_change(sender, instance, action, pk_set, model, **kwargs):
    """Логування змін ManyToMany полів (Owners, Administrators)"""
    try:
        if action == 'post_add':
            added_items = model.objects.filter(pk__in=pk_set)
            item_type = 'owners' if model == AssetOwner else 'administrators'
            action_type = AssetHistory.ACTION_OWNERS_CHANGED if model == AssetOwner else AssetHistory.ACTION_ADMINISTRATORS_CHANGED
            
            details = _("{} added: {}").format(
                _("Owners") if model == AssetOwner else _("Administrators"),
                ", ".join([item.name for item in added_items])
            )
            
            AssetHistory.objects.create(
                asset=instance,
                action=action_type,
                action_by=instance.last_modified_by,
                details=details,
                changes={
                    'type': 'add',
                    'item_type': item_type,
                    'items': [{'id': item.id, 'name': item.name} for item in added_items]
                }
            )
        
        elif action == 'post_remove':
            removed_items = model.objects.filter(pk__in=pk_set)
            item_type = 'owners' if model == AssetOwner else 'administrators'
            action_type = AssetHistory.ACTION_OWNERS_CHANGED if model == AssetOwner else AssetHistory.ACTION_ADMINISTRATORS_CHANGED
            
            details = _("{} removed: {}").format(
                _("Owners") if model == AssetOwner else _("Administrators"),
                ", ".join([item.name for item in removed_items])
            )
            
            AssetHistory.objects.create(
                asset=instance,
                action=action_type,
                action_by=instance.last_modified_by,
                details=details,
                changes={
                    'type': 'remove',
                    'item_type': item_type,
                    'items': [{'id': item.id, 'name': item.name} for item in removed_items]
                }
            )
        
        elif action == 'post_clear':
            item_type = 'owners' if model == AssetOwner else 'administrators'
            action_type = AssetHistory.ACTION_OWNERS_CHANGED if model == AssetOwner else AssetHistory.ACTION_ADMINISTRATORS_CHANGED
            
            details = _("All {} cleared").format(
                _("Owners") if model == AssetOwner else _("Administrators")
            )
            
            AssetHistory.objects.create(
                asset=instance,
                action=action_type,
                action_by=instance.last_modified_by,
                details=details,
                changes={
                    'type': 'clear',
                    'item_type': item_type
                }
            )
    except Exception as e:
        logger.error(f"Error logging M2M change: {str(e)}")


# Реєстрація сигналів для M2M полів
m2m_changed.connect(log_m2m_change, sender=InformationAsset.owners.through)
m2m_changed.connect(log_m2m_change, sender=InformationAsset.administrators.through)
