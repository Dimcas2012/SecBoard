 
import json

from functools import wraps
from hashlib import sha256
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse,FileResponse, Http404, HttpResponseRedirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from .decorators import file_access_required
from .models import RegisterDocs, RelatedDocs, DocType, AccessDocs, DocumentApproval, DocumentFamiliarization, DocStatus, LegislativeDoc, RegulatorName, AccessLegislativeDoc, AccessMandatory, AccessClassification, RegDocsGuide, RegDocsGuideTranslation, LegislativeDocsGuide, LegislativeDocsGuideTranslation
from django.shortcuts import render
import logging
from app_conf.models import Company, CustomGroup, Country
from django.contrib.auth.models import Group, User
from django.utils.translation import get_language, gettext as _, activate as translation_activate
import urllib.parse
import os
from typing import Dict, Any, List, Optional
from app_cabinet.models import CabinetUser, CabinetGroup
from .utils import parse_document_with_google_ai, parse_document_with_ai  # Import the document parsing functions
from app_ai.models import ModelChoice  # Import AI models
from django.contrib import messages
from django.urls import reverse


logger = logging.getLogger(__name__)

logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")


def _get_previous_version_info(doc: RegisterDocs) -> Optional[Dict[str, Any]]:
    """Build previous document info for tooltip: name, type, status, level, date, version, version_history."""
    prev = getattr(doc, 'previous_version', None)
    if not prev:
        return None
    try:
        date_str = prev.date_doc.strftime('%Y-%m-%d') if getattr(prev, 'date_doc', None) else ''
        return {
            'name_doc': prev.name_doc or '',
            'document_type': prev.type_doc.get_name() if prev.type_doc else '',
            'document_status': prev.status_doc.get_name() if prev.status_doc else '',
            'level': prev.access_classification.get_name() if prev.access_classification else '',
            'document_date': date_str,
            'document_version': prev.vers_doc or '',
            'version_history': (prev.version_history or '').strip() or '',
        }
    except Exception as e:
        logger.debug("Error building previous_version_info for doc %s: %s", doc.id, e)
        return None


def _register_doc_file_metadata(doc: RegisterDocs, include_hash: bool = False) -> Optional[Dict[str, Any]]:
    """Build file_doc payload for JSON APIs; never raises if the file is missing on disk."""
    if not doc.file_doc or not doc.file_doc.name:
        return None
    name = doc.file_doc.name
    storage = doc.file_doc.storage
    try:
        exists_on_disk = bool(storage.exists(name))
    except Exception:
        exists_on_disk = False
    try:
        file_url = doc.file_doc.url
    except Exception:
        file_url = ''
    meta: Dict[str, Any] = {
        'exists': exists_on_disk,
        'url': file_url,
        'name': os.path.basename(name),
        'size': doc.file_size,
    }
    if include_hash:
        meta['hash'] = doc.calculate_file_hash()
    return meta


def format_document_data(doc: RegisterDocs, current_language: str) -> Dict[str, Any]:
    """Format document data for JSON response with extended approval and hash information."""
    try:
        # Get file information (tolerate missing files on disk)
        try:
            file_data = _register_doc_file_metadata(doc, include_hash=True)
        except Exception as e:
            logger.error(f"Error processing file data for document {doc.id}: {str(e)}", exc_info=True)
            file_data = None

        # Status strings: default is English; other languages via Django Translations (.po)
        _lang = (current_language or 'en')[:2]
        _prev_lang = get_language() or 'en'
        translation_activate(_lang)
        try:
            _status_approved = _('Approved')
            _status_pending = _('Pending')
            _status_needs_reapproval = _('Needs reapproval')
        finally:
            translation_activate(_prev_lang)
        _status_by_key = {
            'approved': _status_approved,
            'pending': _status_pending,
            'needs_reapproval': _status_needs_reapproval,
        }
        logger.debug(f"Current language: {current_language}, display lang: {_lang}")

        # Prepare document type data
        type_doc_data = None
        if doc.type_doc:
            type_doc_data = {
                'id': doc.type_doc.id,
                'text': doc.type_doc.get_name() if doc.type_doc else '',
                'color': doc.type_doc.color
            }

        # Prepare document status data
        status_doc_data = None
        if doc.status_doc:
            status_doc_data = {
                'id': doc.status_doc.id,
                'text': doc.status_doc.get_name(),
                'color': doc.status_doc.color
            }

        # Prepare access classification data
        access_classification_data = None
        if doc.access_classification:
            access_classification_data = {
                'id': doc.access_classification.id,
                'text': doc.access_classification.get_name(),
                'color': doc.access_classification.color,
                'icon': doc.access_classification.icon
            }

        # Handle date formatting
        formatted_date = ''
        if doc.date_doc:
            if isinstance(doc.date_doc, str):
                try:
                    # Parse string date to datetime object
                    parsed_date = parse_date(doc.date_doc)
                    if parsed_date:
                        formatted_date = parsed_date.strftime('%Y-%m-%d')
                    else:
                        formatted_date = doc.date_doc
                except ValueError:
                    # If parsing fails, use the original string
                    formatted_date = doc.date_doc
            else:
                # If it's already a date object, format it
                formatted_date = doc.date_doc.strftime('%Y-%m-%d')

        # Format approvals data
        try:
            approvals = DocumentApproval.objects.filter(document=doc).select_related(
                'approver',
                'approver__cabinet'
            ).order_by('approved_at')

            approvals_data = []
            for approval in approvals:
                if approval.approver:
                    try:
                        cabinet_user = approval.approver.cabinet
                        position_data = None
                        department_data = None

                        if cabinet_user:
                            if cabinet_user.position:
                                position_data = {
                                    'ua': cabinet_user.position.get_name('ua') or cabinet_user.position.get_name('uk'),
                                    'en': cabinet_user.position.get_name('en'),
                                    'ru': cabinet_user.position.get_name('ru')
                                }
                                logger.debug(f"Position data for user {approval.approver.id}: {position_data}")
                            else:
                                logger.warning(f"No position found for user {approval.approver.id}")

                            if cabinet_user.department:
                                department_data = {
                                    'ua': cabinet_user.department.get_name('ua') or cabinet_user.department.get_name('uk'),
                                    'en': cabinet_user.department.get_name('en'),
                                    'ru': cabinet_user.department.get_name('ru')
                                }
                                logger.debug(f"Department data for user {approval.approver.id}: {department_data}")
                            else:
                                logger.warning(f"No department found for user {approval.approver.id}")

                        # Localized display names (site language) for Document Approvers
                        position_name = (cabinet_user.position.get_name() or '') if (cabinet_user and cabinet_user.position) else None
                        department_name = (cabinet_user.department.get_name() or '') if (cabinet_user and cabinet_user.department) else None
                        approver_data = {
                            'approver_id': str(approval.approver.id),
                            'approver_name': approval.approver.get_full_name() or approval.approver.username,
                            'department': department_data,
                            'department_name': department_name,
                            'position': position_data,
                            'position_name': position_name,
                            'approval_date': approval.approved_at.isoformat() if approval.approved_at else None,
                            'document_hash': approval.document_hash or '',
                            'status': _status_by_key.get(approval.status, _status_pending),
                            'status_key': approval.status,
                        }
                        logger.debug(f"Approval data for document {doc.id}: {approver_data}")
                        approvals_data.append(approver_data)
                    except Exception as e:
                        logger.error(f"Error processing approval {approval.id} for document {doc.id}: {str(e)}",
                                   exc_info=True)
                        continue
        except Exception as e:
            logger.error(f"Error processing approvals for document {doc.id}: {str(e)}", exc_info=True)
            approvals_data = []

        # Format familiarization (acknowledgment) data
        doc_hash = doc.document_hash or ''
        try:
            familiarizations = DocumentFamiliarization.objects.filter(document=doc).select_related(
                'user', 'user__cabinet', 'user__cabinet__position', 'user__cabinet__department'
            ).order_by('-acknowledged_at')
            familiarization_data = []
            for fam in familiarizations:
                if fam.user:
                    try:
                        cabinet_user = getattr(fam.user, 'cabinet', None)
                        position_name = (cabinet_user.position.get_name() or '') if (cabinet_user and cabinet_user.position) else None
                        department_name = (cabinet_user.department.get_name() or '') if (cabinet_user and cabinet_user.department) else None
                        familiarization_data.append({
                            'user_id': str(fam.user.id),
                            'user_name': fam.user.get_full_name() or fam.user.username,
                            'position_name': position_name,
                            'department_name': department_name,
                            'acknowledged_at': fam.acknowledged_at.isoformat() if fam.acknowledged_at else None,
                            'document_hash': fam.document_hash or '',
                            'hash_valid': (fam.document_hash or '') == doc_hash,
                        })
                    except Exception as e:
                        logger.error(f"Error processing familiarization {fam.id}: {str(e)}", exc_info=True)
                        continue
        except Exception as e:
            logger.error(f"Error processing familiarizations for document {doc.id}: {str(e)}", exc_info=True)
            familiarization_data = []

        # Get related documents data
        try:
            related_docs_data = [{
                'id': rel_doc.id,
                'name': rel_doc.name_rel_doc,
                'company': rel_doc.company.name if rel_doc.company else None,
                'version': rel_doc.vers_rel_doc,
                'date': rel_doc.date_rel_doc.strftime('%Y-%m-%d') if rel_doc.date_rel_doc else None
            } for rel_doc in doc.related_docs.all()]
        except Exception as e:
            logger.error(f"Error processing related documents for document {doc.id}: {str(e)}", exc_info=True)
            related_docs_data = []

        # Get groups info
        try:
            groups_info = [{
                'id': group.id,
                'name': group.name,
                'description': group.customgroup.description_group if hasattr(group, 'customgroup') else ''
            } for group in doc.groups.select_related('customgroup').all()]
        except Exception as e:
            logger.error(f"Error processing groups for document {doc.id}: {str(e)}", exc_info=True)
            groups_info = []

        # Get allowed users (Cabinet users) info for list display
        try:
            allowed_users_info = [{
                'id': u.id,
                'name': u.get_full_name() or u.username,
            } for u in doc.allowed_users.all()]
        except Exception as e:
            logger.error(f"Error processing allowed_users for document {doc.id}: {str(e)}", exc_info=True)
            allowed_users_info = []

        # Users with access (Groups + Cabinet users) for Familiarization modal and count
        access_users_list = []
        try:
            group_user_ids = set(
                User.objects.filter(groups__in=doc.groups.all()).values_list('id', flat=True)
            )
            allowed_user_ids = set(doc.allowed_users.values_list('id', flat=True))
            access_user_ids = group_user_ids | allowed_user_ids
            access_user_count = len(access_user_ids)
            if access_user_ids:
                access_users = User.objects.filter(
                    id__in=access_user_ids
                ).select_related('cabinet', 'cabinet__position', 'cabinet__department')
                for u in access_users:
                    cabinet = getattr(u, 'cabinet', None)
                    position_name = (cabinet.position.get_name() or '') if (cabinet and getattr(cabinet, 'position', None)) else None
                    department_name = (cabinet.department.get_name() or '') if (cabinet and getattr(cabinet, 'department', None)) else None
                    access_users_list.append({
                        'user_id': str(u.id),
                        'user_name': u.get_full_name() or u.username,
                        'position_name': position_name,
                        'department_name': department_name,
                    })
        except Exception as e:
            logger.error(f"Error building access users for document {doc.id}: {str(e)}", exc_info=True)
            access_user_count = 0

        # Get creator/updater information safely
        try:
            created_by = None
            if doc.created_by_id:
                try:
                    user = User.objects.select_related('cabinet').get(id=doc.created_by_id)
                    created_by = user.get_full_name() or user.username
                except User.DoesNotExist:
                    logger.warning(f"Created by user {doc.created_by_id} for document {doc.id} not found")

            updated_by = None
            if doc.updated_by_id:
                try:
                    user = User.objects.select_related('cabinet').get(id=doc.updated_by_id)
                    updated_by = user.get_full_name() or user.username
                except User.DoesNotExist:
                    logger.warning(f"Updated by user {doc.updated_by_id} for document {doc.id} not found")
        except Exception as e:
            logger.error(f"Error getting user information for document {doc.id}: {str(e)}", exc_info=True)
            created_by = updated_by = None

        # Compile all data
        formatted_data = {
            'id': doc.id,
            'name_doc': doc.name_doc,
            'company': {'id': doc.company.id, 'name': doc.company.name} if doc.company else None,
            'type_doc': type_doc_data,
            'status_doc': status_doc_data,
            'access_classification': access_classification_data,
            'vers_doc': doc.vers_doc,
            'date_doc': formatted_date,
            'version_history': (doc.version_history or '').strip() or '',
            'description': doc.description,
            'html_version': bool(doc.vers_doc_html),
            'vers_doc_html': doc.vers_doc_html,
            'file': file_data,
            'approval': {
                'is_approved': doc.is_approved,
                'status': _status_approved if doc.is_approved else _status_pending,
                'approvals': approvals_data
            },
            'familiarization': {
                'acknowledgments': familiarization_data,
                'document_hash': doc_hash,
                'access_user_count': access_user_count,
                'access_users_list': access_users_list,
            },
            'related_docs': related_docs_data,
            'related_docs_count': len(related_docs_data),
            'previous_version_id': getattr(doc, 'previous_version_id', None),
            'previous_version_info': _get_previous_version_info(doc),
            'groups': list(doc.groups.values_list('id', flat=True)),
            'groups_info': groups_info,
            'allowed_users_info': allowed_users_info,
            'document_hash': doc.document_hash,
            'created_at': doc.created_at.isoformat() if doc.created_at else None,
            'updated_at': doc.updated_at.isoformat() if doc.updated_at else None,
            'created_by': created_by,
            'updated_by': updated_by
        }

        return formatted_data

    except Exception as e:
        logger.error(f"Error formatting document {doc.id}: {str(e)}", exc_info=True)
        raise ValidationError(f"Error formatting document data: {str(e)}")

def prepare_doc_types_data(doc_types: List[DocType]) -> List[Dict[str, Any]]:
    """Prepare document types data for template context (uses translations when available, same as Document Status)."""
    from app_conf.models import Country
    countries = {c.code: c for c in Country.objects.filter(code__in=['UA', 'GB', 'RU', 'US'])}
    ua, gb, ru = countries.get('UA'), countries.get('GB') or countries.get('US'), countries.get('RU')
    return [{
        'id': dt.id,
        'name': {
            'uk': (dt.get_local_name(ua) or dt.name or '') if ua else (dt.name or ''),
            'en': (dt.get_local_name(gb) or dt.name or '') if gb else (dt.name or ''),
            'ru': (dt.get_local_name(ru) or dt.name or '') if ru else (dt.name or '')
        },
        'description': {
            'uk': (dt.get_local_description(ua) or dt.description or '') if ua else (dt.description or ''),
            'en': (dt.get_local_description(gb) or dt.description or '') if gb else (dt.description or ''),
            'ru': (dt.get_local_description(ru) or dt.description or '') if ru else (dt.description or '')
        },
        'color': dt.color
    } for dt in doc_types]

def prepare_doc_statuses_data(doc_statuses: List[DocStatus]) -> List[Dict[str, Any]]:
    """Prepare document statuses data for template context (uses translations when available, same as Asset Type)."""
    from app_conf.models import Country
    countries = {c.code: c for c in Country.objects.filter(code__in=['UA', 'GB', 'RU', 'US'])}
    ua, gb, ru = countries.get('UA'), countries.get('GB') or countries.get('US'), countries.get('RU')
    return [{
        'id': dt.id,
        'name': {
            'uk': (dt.get_local_name(ua) or dt.name or '') if ua else (dt.name or ''),
            'en': (dt.get_local_name(gb) or dt.name or '') if gb else (dt.name or ''),
            'ru': (dt.get_local_name(ru) or dt.name or '') if ru else (dt.name or '')
        },
        'description': {
            'uk': (dt.get_local_description(ua) or dt.description or '') if ua else (dt.description or ''),
            'en': (dt.get_local_description(gb) or dt.description or '') if gb else (dt.description or ''),
            'ru': (dt.get_local_description(ru) or dt.description or '') if ru else (dt.description or '')
        },
        'color': dt.color
    } for dt in doc_statuses]

def prepare_access_classifications_data(access_classifications) -> List[Dict[str, Any]]:
    """Prepare access classifications data for template context (uses translations when available, same as DocStatus/DocType)."""
    from app_conf.models import Country
    countries = {c.code: c for c in Country.objects.filter(code__in=['UA', 'GB', 'RU', 'US'])}
    ua, gb, ru = countries.get('UA'), countries.get('GB') or countries.get('US'), countries.get('RU')
    return [{
        'id': ac.id,
        'name': {
            'uk': ac.get_local_name(ua) if ua else ac.get_name(),
            'en': ac.get_local_name(gb) if gb else ac.get_name(),
            'ru': ac.get_local_name(ru) if ru else ac.get_name()
        },
        'description': {
            'uk': ac.get_local_description(ua) if ua else ac.get_description(),
            'en': ac.get_local_description(gb) if gb else ac.get_description(),
            'ru': ac.get_local_description(ru) if ru else ac.get_description()
        },
        'color': ac.color,
        'icon': ac.icon
    } for ac in access_classifications]

@login_required
@ensure_csrf_cookie
@login_required
def get_file_content(request, doc_id):
    try:
        doc = RegisterDocs.objects.get(id=doc_id)
        if not doc.has_access(request.user):
            return JsonResponse({
                'success': False,
                'error': _('Access denied')
            }, status=403)

        if not doc.file_doc:
            return JsonResponse({
                'success': False,
                'error': _('No file attached')
            }, status=404)

        # Перевіряємо чи не було змін у файлі
        doc.file_doc.seek(0)

        # Читаємо файл по частинам
        file_content = b''
        for chunk in doc.file_doc.chunks():
            file_content += chunk

        # Оновлюємо хеш документа
        current_hash = sha256(file_content).hexdigest()
        if current_hash != doc.document_hash:
            doc.document_hash = current_hash
            doc.save()

        return JsonResponse({
            'success': True,
            'content': file_content.hex(),
            'hash': current_hash
        })


    except RegisterDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)

    except Exception as e:
        logger.error(f"Error getting file content: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def check_user_edit_access(user):
    """Check if user has edit access based on AccessDocs"""
    if user.is_superuser:
        return True

    user_groups = user.groups.all()
    # Перевіряємо права на редагування
    access_docs = AccessDocs.objects.filter(
        group__in=user_groups,
        has_access=True,
        can_edit=True
    ).exists()

    return access_docs


# Додаємо нову функцію перевірки прав на погодження
def check_approval_access(user, doc_id):
    """Check if user has approval access for the document"""
    try:
        document = RegisterDocs.objects.get(id=doc_id)
        approval = DocumentApproval.objects.filter(
            document=document,
            approver=user
        ).first()

        return bool(approval)
    except RegisterDocs.DoesNotExist:
        return False

def get_user_access_level(user):
    """Get user's access level details for regular documents"""
    # print('user = ', user)
    if user.is_superuser:
        return {
            'has_access': True,
            'can_edit': True,
            'show_link': True
        }

    access = AccessDocs.objects.filter(
        group__in=user.groups.all(),
        has_access=True
    ).first()
    # print('access = ', access)
    if access:
        return {
            'has_access': True,
            'can_edit': access.can_edit,
            'show_link': access.has_access
        }

    return {
        'has_access': False,
        'can_edit': False,
        'show_link': False
    }

def get_legislative_user_access_level(user):
    """Get user's access level details for legislative documents"""
    if user.is_superuser:
        return {
            'has_access': True,
            'can_edit': True,
            'show_link': True
        }

    access = AccessLegislativeDoc.objects.filter(
        group__in=user.groups.all(),
        has_access=True
    ).first()
    
    if access:
        return {
            'has_access': True,
            'can_edit': access.can_edit,
            'show_link': access.show_link
        }

    # Fallback to regular document access if there's no specific legislative access
    regular_access = get_user_access_level(user)
    if regular_access['has_access']:
        return regular_access

    return {
        'has_access': False,
        'can_edit': False,
        'show_link': False
    }

def get_mandatory_user_access_level(user):
    """Get user's access level details for mandatory processes"""
    if user.is_superuser:
        return {
            'has_access': True,
            'can_edit': True,
            'show_link': True
        }

    # Check if user has access through their groups
    access = AccessMandatory.objects.filter(
        group__in=user.groups.all(),
        has_access=True
    ).first()
    
    if access:
        # If user has a company, check if it's in the allowed companies
        if hasattr(user, 'cabinet') and user.cabinet.company:
            user_company = user.cabinet.company
            # If no specific companies are set, allow access to all
            if not access.companies.exists() or access.companies.filter(id=user_company.id).exists():
                return {
                    'has_access': True,
                    'can_edit': access.can_edit,
                    'show_link': True
                }
        else:
            # User has no company, allow access if no company restrictions
            if not access.companies.exists():
                return {
                    'has_access': True,
                    'can_edit': access.can_edit,
                    'show_link': True
                }

    return {
        'has_access': False,
        'can_edit': False,
        'show_link': False
    }

def get_user_allowed_companies(user):
    """Get list of companies that user can access based on AccessMandatory settings"""
    if user.is_superuser:
        # Superuser can access all companies
        from app_conf.models import Company
        return Company.objects.all()
    
    user_groups = user.groups.all()
    # Get all AccessMandatory records for user's groups
    access_records = AccessMandatory.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    if not access_records.exists():
        return []
    
    # Collect all allowed companies from all access records
    allowed_companies = set()
    for access in access_records:
        if access.companies.exists():
            # If specific companies are set, add them
            allowed_companies.update(access.companies.all())
        else:
            # If no specific companies are set, user can access all companies
            from app_conf.models import Company
            return Company.objects.all()
    
    return list(allowed_companies)

def get_user_allowed_doc_companies(user):
    """Get list of companies that user can access for documents based on AccessDocs settings"""
    if user.is_superuser:
        # Superuser can access all companies
        from app_conf.models import Company
        return Company.objects.all()
    
    user_groups = user.groups.all()
    # Get all AccessDocs records for user's groups
    access_records = AccessDocs.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    if not access_records.exists():
        return []
    
    # Collect all allowed companies from all access records
    allowed_companies = set()
    for access in access_records:
        if access.companies.exists():
            # If specific companies are set, add them
            allowed_companies.update(access.companies.all())
        else:
            # If no specific companies are set, user can access all companies
            from app_conf.models import Company
            return Company.objects.all()
    
    return list(allowed_companies)

def check_user_mandatory_edit_access(user):
    """Check if user has edit access for mandatory processes"""
    if user.is_superuser:
        return True

    user_groups = user.groups.all()
    
    # Check for specific mandatory access
    mandatory_access = AccessMandatory.objects.filter(
        group__in=user_groups,
        has_access=True,
        can_edit=True
    ).first()
    
    if mandatory_access:
        # If user has a company, check if it's in the allowed companies
        if hasattr(user, 'cabinet') and user.cabinet.company:
            user_company = user.cabinet.company
            # If no specific companies are set, allow access to all
            if not mandatory_access.companies.exists() or mandatory_access.companies.filter(id=user_company.id).exists():
                return True
        else:
            # User has no company, allow access if no company restrictions
            if not mandatory_access.companies.exists():
                return True

    return False

def check_user_legislative_edit_access(user):
    """Check if user has edit access for legislative documents"""
    if user.is_superuser:
        return True

    user_groups = user.groups.all()
    # Check for specific legislative access first
    legislative_access = AccessLegislativeDoc.objects.filter(
        group__in=user_groups,
        has_access=True,
        can_edit=True
    ).exists()
    
    if legislative_access:
        return True
        
    # Fallback to regular document access
    return check_user_edit_access(user)


# Modify the existing decorators
# Змінюємо декоратор user_can_edit
def user_can_edit(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Якщо це запит на погодження документа, перевіряємо права на погодження
        if view_func.__name__ == 'approve_document':
            doc_id = kwargs.get('doc_id')
            if check_approval_access(request.user, doc_id):
                return view_func(request, *args, **kwargs)
        # For legislative document operations
        elif view_func.__name__ in ['add_legislative_doc', 'edit_legislative_doc', 'delete_legislative_doc']:
            if check_user_legislative_edit_access(request.user):
                return view_func(request, *args, **kwargs)
        # For mandatory process operations
        elif view_func.__name__ in ['add_mandatory_process', 'edit_mandatory_process', 'delete_mandatory_process', 'mark_process_completed']:
            if check_user_mandatory_edit_access(request.user):
                return view_func(request, *args, **kwargs)
        # Для інших операцій перевіряємо права на редагування
        elif check_user_edit_access(request.user):
            return view_func(request, *args, **kwargs)

        return JsonResponse({
            'success': False,
            'error': _('You do not have permission to perform this action')
        }, status=403)

    return _wrapped_view


@login_required
def reg_docs(request):
    try:
        user_access = get_user_access_level(request.user)
        if not user_access['has_access']:
            return JsonResponse({
                'success': False,
                'error': _('Access denied')
            }, status=403)

        user_groups = request.user.groups.all()
        register_docs = RegisterDocs.objects.filter(
            Q(groups__in=user_groups) | Q(allowed_users=request.user)
        ).distinct()

        # Handle AJAX request for getting company users
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if request.GET.get('action') == 'get_company_users':
                return handle_company_users_request(request)

            # Handle DataTables AJAX request
            try:
                start = int(request.GET.get('start', 0))
                length = int(request.GET.get('length', 25))
                draw = int(request.GET.get('draw', 1))

                # Apply filters
                filter_company = request.GET.get('filter_company')
                filter_type = request.GET.get('filter_type')
                filter_date_from = request.GET.get('filter_date_from')
                filter_date_to = request.GET.get('filter_date_to')
                filter_approval = request.GET.get('filter_approval')
                filter_status = request.GET.get('filter_status')
                filter_access = request.GET.get('filter_access')
                filter_doc_id = request.GET.get('filter_doc_id')

                if filter_doc_id:
                    try:
                        register_docs = register_docs.filter(id=int(filter_doc_id))
                    except (TypeError, ValueError):
                        pass

                if filter_company:
                    register_docs = register_docs.filter(company_id=filter_company)
                
                if filter_type:
                    register_docs = register_docs.filter(type_doc_id=filter_type)
                
                if filter_date_from:
                    register_docs = register_docs.filter(date_doc__gte=filter_date_from)
                
                if filter_date_to:
                    register_docs = register_docs.filter(date_doc__lte=filter_date_to)
                
                if filter_access:
                    register_docs = register_docs.filter(access_classification_id=filter_access)
                
                if filter_status:
                    register_docs = register_docs.filter(status_doc_id=filter_status)
                
                # Note: filter_approval requires additional logic with DocumentApproval model
                # This will be handled separately if needed
                
                # Apply global search
                search_value = request.GET.get('search[value]', '').strip()
                if search_value:
                    register_docs = register_docs.filter(
                        Q(name_doc__icontains=search_value) |
                        Q(description__icontains=search_value) |
                        Q(company__name__icontains=search_value) |
                        Q(type_doc__name__icontains=search_value) |
                        Q(type_doc__name_local__icontains=search_value) |
                        Q(type_doc__code__icontains=search_value) |
                        Q(status_doc__name__icontains=search_value) |
                        Q(status_doc__name_local__icontains=search_value) |
                        Q(status_doc__code__icontains=search_value) |
                        Q(access_classification__name__icontains=search_value) |
                        Q(access_classification__code__icontains=search_value) |
                        Q(access_classification__translations__name_local__icontains=search_value) |
                        Q(vers_doc__icontains=search_value)
                    ).distinct()

                # Get total record count
                total = RegisterDocs.objects.filter(
                    Q(groups__in=user_groups) | Q(allowed_users=request.user)
                ).distinct().count()


                # Get filtered count
                filtered_total = register_docs.count()

                # Order: map frontend column index to model field (matches mainDocsTable columns)
                order_column = int(request.GET.get('order[0][column]', 3))
                order_dir = request.GET.get('order[0][dir]', 'desc')
                order_columns = [
                    'name_doc',              # 0 Name
                    'company__name',         # 1 Company
                    'type_doc__name',        # 2 Type
                    'date_doc',              # 3 Vers/Date
                    'description',           # 4 Description
                    None, None, None,        # 5-7 HTML/File, Related, Previous
                    None, None,              # 8-9 Approval, Familiarization
                    'status_doc__name',      # 10 Status
                    'access_classification__sort_order',  # 11 Level
                    None, None,              # 12-13 Access, Actions (when can_edit)
                ]
                order_field = None
                if order_column < len(order_columns) and order_columns[order_column] is not None:
                    order_field = order_columns[order_column]
                    if order_dir == 'desc':
                        order_field = f'-{order_field}'
                if order_field:
                    register_docs = register_docs.order_by('status_doc__sort_order', order_field)
                else:
                    register_docs = register_docs.order_by('status_doc__sort_order', '-date_doc', 'name_doc')

                # Select previous_version and its type/status/level for tooltip
                register_docs = register_docs.select_related(
                    'previous_version',
                    'previous_version__type_doc',
                    'previous_version__status_doc',
                    'previous_version__access_classification',
                )
                # Prefetch groups and allowed_users for list display
                register_docs = register_docs.prefetch_related(
                    'groups', 'groups__customgroup', 'allowed_users'
                )
                # Apply pagination
                register_docs = register_docs[start:start + length]

                # Format data
                docs_data = []
                for doc in register_docs:
                    formatted_doc = format_document_data(doc, get_language())
                    formatted_doc['can_edit'] = user_access['can_edit']
                    docs_data.append(formatted_doc)

                return JsonResponse({
                    'draw': draw,
                    'recordsTotal': total,
                    'recordsFiltered': filtered_total,
                    'data': docs_data
                })

            except Exception as e:
                logger.error(f"Error processing DataTables request: {str(e)}", exc_info=True)
                return JsonResponse({
                    'error': str(e)
                }, status=500)

        # Regular page load context
        cabinet_groups = CabinetGroup.objects.select_related('group').all()
        related_docs = RelatedDocs.objects.filter(groups__in=user_groups).distinct()

        # Get all cabinet users for initial load
        all_cabinet_users = CabinetUser.objects.filter(
            user__is_active=True
        ).select_related('user', 'position', 'department')

        # Get companies that user can access based on AccessDocs settings
        allowed_companies = get_user_allowed_doc_companies(request.user)
        
        # Log for debugging
        logger.info(f"User {request.user.email} allowed companies: {[c.name for c in allowed_companies]}")
        
        # Get unique values that are actually present in user's documents
        used_company_ids = list(register_docs.values_list('company_id', flat=True).distinct())
        used_type_ids = list(register_docs.values_list('type_doc_id', flat=True).distinct())
        used_status_ids = list(register_docs.values_list('status_doc_id', flat=True).distinct())
        used_access_ids = list(register_docs.values_list('access_classification_id', flat=True).distinct())
        
        # Filter companies to only those used in documents
        # allowed_companies is a list, not a QuerySet
        if isinstance(allowed_companies, list):
            used_companies = [c for c in allowed_companies if c.id in used_company_ids]
        else:
            used_companies = allowed_companies.filter(id__in=used_company_ids)
        
        # Filter doc types, statuses and access classifications to only those used in documents
        used_doc_types = DocType.objects.filter(id__in=used_type_ids)
        used_doc_statuses = DocStatus.objects.filter(id__in=used_status_ids)
        used_access_classifications = AccessClassification.objects.filter(id__in=used_access_ids, is_active=True)
        
        # Get unique approval statuses from documents
        doc_ids = list(register_docs.values_list('id', flat=True))
        approval_statuses = DocumentApproval.objects.filter(
            document_id__in=doc_ids
        ).values_list('status', flat=True).distinct()
        
        # Convert approval statuses to list (will be used in frontend)
        approval_statuses_list = list(approval_statuses) if approval_statuses else []
        
        # Prepare filtered data for filters
        companies_data = [{'id': c.id, 'name': c.name} for c in used_companies]
        
        # Get access classifications ordered by priority
        access_classifications = AccessClassification.objects.filter(is_active=True).order_by('sort_order', 'id')

        # Display data for modals (from Document Type / Document Status Translations only)
        doc_types_qs = DocType.objects.filter(is_active=True).order_by('name', 'name_local')
        doc_statuses_qs = DocStatus.objects.filter(is_active=True).order_by('sort_order', 'id')
        doc_types_display = prepare_doc_types_data(list(doc_types_qs))
        doc_statuses_display = prepare_doc_statuses_data(list(doc_statuses_qs))
        current_lang = (get_language() or 'en')[:2]
        for d in doc_types_display:
            d['current_name'] = d['name'].get(current_lang) or d['name'].get('en') or d['name'].get('uk') or ''
        for d in doc_statuses_display:
            d['current_name'] = d['name'].get(current_lang) or d['name'].get('en') or d['name'].get('uk') or ''

        context = {
            'companies': allowed_companies,
            'groups': cabinet_groups,
            'doc_types': doc_types_qs,
            'doc_statuses': doc_statuses_qs,
            'doc_types_display': doc_types_display,
            'doc_statuses_display': doc_statuses_display,
            'access_classifications': access_classifications,
            'user_access': user_access,
            'current_language': get_language(),
            'doc_types_data': json.dumps(prepare_doc_types_data(used_doc_types)),
            'doc_statuses_data': json.dumps(prepare_doc_statuses_data(used_doc_statuses)),
            'access_classifications_data': json.dumps(prepare_access_classifications_data(used_access_classifications)),
            'companies_data': json.dumps(companies_data),
            'approval_statuses': json.dumps(approval_statuses_list),
            'related_docs': related_docs,
            'cabinet_users': all_cabinet_users
        }
        return render(request, 'app_doc/reg_docs.html', context)

    except Exception as e:
        logger.error(f"Error in reg_docs view: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def reg_docs_guide(request):
    """Return JSON { content: html } for the Document Registry (reg_docs) guide (localized)."""
    user_access = get_user_access_level(request.user)
    if not user_access.get('has_access'):
        return JsonResponse({'content': ''})
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = RegDocsGuide.objects.first()
    if guide:
        if country:
            trans = RegDocsGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = RegDocsGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def reg_docs_guide_translate(request):
    """API for AI translation of Reg Docs guide content (admin)."""
    try:
        data = json.loads(request.body)
        text = (data.get('text') or '').strip()
        country_id = data.get('country_id')
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
        if not country_id:
            return JsonResponse({'error': 'Country ID is required'}, status=400)
        country = Country.objects.get(id=country_id)
    except Country.DoesNotExist:
        return JsonResponse({'error': 'Country not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    lang_map = {
        'ua': 'uk', 'gb': 'en', 'us': 'en', 'uk': 'en', 'ru': 'ru',
        'kz': 'kk', 'by': 'be', 'md': 'ro', 'ge': 'ka', 'am': 'hy', 'az': 'az',
        'ch': 'de', 'at': 'de', 'be': 'nl', 'dk': 'da', 'no': 'no', 'se': 'sv',
        'fi': 'fi', 'ee': 'et', 'lv': 'lv', 'lt': 'lt', 'cz': 'cs', 'sk': 'sk',
        'hu': 'hu', 'ro': 'ro', 'bg': 'bg', 'pl': 'pl', 'fr': 'fr', 'es': 'es',
        'it': 'it', 'cn': 'zh-cn', 'jp': 'ja', 'kr': 'ko', 'tr': 'tr',
    }
    target = lang_map.get(country.code.lower(), country.code.lower())
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target=target)
        translated = translator.translate(text)
        return JsonResponse({
            'success': True,
            'translated_text': translated,
            'target_language': target,
            'country_name': country.name,
        })
    except Exception as e:
        err = str(e)
        if 'No support for the provided language' in err:
            return JsonResponse({
                'success': True,
                'translated_text': text,
                'target_language': target,
                'country_name': country.name,
                'warning': 'Language not supported, returned original',
            })
        return JsonResponse({'success': False, 'error': err}, status=500)


@login_required
@require_http_methods(["GET"])
def legislative_docs_guide(request):
    """Return JSON { content: html } for the Legislative Documents guide (localized)."""
    user_access = get_legislative_user_access_level(request.user)
    if not user_access.get('has_access'):
        return JsonResponse({'content': ''})
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = LegislativeDocsGuide.objects.first()
    if guide:
        if country:
            trans = LegislativeDocsGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = LegislativeDocsGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def legislative_docs_guide_translate(request):
    """API for AI translation of Legislative Docs guide content (admin)."""
    try:
        data = json.loads(request.body)
        text = (data.get('text') or '').strip()
        country_id = data.get('country_id')
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
        if not country_id:
            return JsonResponse({'error': 'Country ID is required'}, status=400)
        country = Country.objects.get(id=country_id)
    except Country.DoesNotExist:
        return JsonResponse({'error': 'Country not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    lang_map = {
        'ua': 'uk', 'gb': 'en', 'us': 'en', 'uk': 'en', 'ru': 'ru',
        'kz': 'kk', 'by': 'be', 'md': 'ro', 'ge': 'ka', 'am': 'hy', 'az': 'az',
        'ch': 'de', 'at': 'de', 'be': 'nl', 'dk': 'da', 'no': 'no', 'se': 'sv',
        'fi': 'fi', 'ee': 'et', 'lv': 'lv', 'lt': 'lt', 'cz': 'cs', 'sk': 'sk',
        'hu': 'hu', 'ro': 'ro', 'bg': 'bg', 'pl': 'pl', 'fr': 'fr', 'es': 'es',
        'it': 'it', 'cn': 'zh-cn', 'jp': 'ja', 'kr': 'ko', 'tr': 'tr',
    }
    target = lang_map.get(country.code.lower(), country.code.lower())
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target=target)
        translated = translator.translate(text)
        return JsonResponse({
            'success': True,
            'translated_text': translated,
            'target_language': target,
            'country_name': country.name,
        })
    except Exception as e:
        err = str(e)
        if 'No support for the provided language' in err:
            return JsonResponse({
                'success': True,
                'translated_text': text,
                'target_language': target,
                'country_name': country.name,
                'warning': 'Language not supported, returned original',
            })
        return JsonResponse({'success': False, 'error': err}, status=500)


def handle_company_users_request(request):
    """Handle AJAX request for company users"""
    company_id = request.GET.get('company_id')
    if not company_id:
        return JsonResponse({
            'success': False,
            'error': _('Company ID is required')
        }, status=400)

    try:
        cabinet_users = CabinetUser.objects.filter(
            company_id=company_id,
            user__is_active=True
        ).select_related(
            'user',
            'position',
            'department'
        ).distinct()

        users_data = [{
            'id': cu.user.id,
            'username': cu.user.username,
            'full_name': cu.user.get_full_name() or cu.user.username,
            'position': cu.position.get_name() if cu.position else None,
            'department': cu.department.get_name() if cu.department else None,
            'email': cu.user.email,
            'is_active': True
        } for cu in cabinet_users]

        return JsonResponse({
            'success': True,
            'users': users_data
        })

    except Exception as e:
        logger.error(f"Error getting company users: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_can_edit
def add_register_doc(request):
    """View for adding new register document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            # Get DocType instance
            doc_type_id = request.POST.get('type_doc')
            try:
                doc_type = DocType.objects.get(id=doc_type_id)
            except DocType.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': _('Invalid document type')
                }, status=400)

            # Get DocStatus instance if provided
            doc_status_id = request.POST.get('status_doc')
            try:
                doc_status = DocStatus.objects.get(id=doc_status_id)
            except DocStatus.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': _('Invalid document status')
                }, status=400)

            # Get AccessClassification instance if provided
            access_classification = None
            access_classification_id = request.POST.get('access_classification')
            if access_classification_id:
                try:
                    access_classification = AccessClassification.objects.get(id=access_classification_id)
                except AccessClassification.DoesNotExist:
                    logger.warning(f'Invalid access classification ID: {access_classification_id}')

            # Create new RegisterDocs instance
            prev_version_id = request.POST.get('previous_version') or None
            if prev_version_id:
                try:
                    prev_version_id = int(prev_version_id)
                except (TypeError, ValueError):
                    prev_version_id = None

            register_doc = RegisterDocs(
                name_doc=request.POST.get('name_doc'),
                company_id=request.POST.get('company'),
                type_doc=doc_type,
                status_doc=doc_status,
                access_classification=access_classification,
                vers_doc=request.POST.get('vers_doc'),
                previous_version_id=prev_version_id,
                vers_doc_html=request.POST.get('vers_doc_html'),
                version_history=request.POST.get('version_history') or None,
                date_doc=request.POST.get('date_doc'),
                description=request.POST.get('description'),
                created_by=request.user,
                updated_by=request.user
            )

            # Handle file upload
            if 'file_doc' in request.FILES:
                register_doc.file_doc = request.FILES['file_doc']
                # Calculate initial hash for the document
                register_doc.document_hash = register_doc.calculate_file_hash()

            # Save the document
            register_doc.save()

            # Add groups and allowed users (at least one required)
            groups = request.POST.getlist('groups[]')
            allowed_user_ids = request.POST.getlist('allowed_users[]')
            if not groups and not allowed_user_ids:
                raise ValidationError(_('Select at least one: Groups and/or Cabinet users.'))
            register_doc.groups.set(groups or [])
            register_doc.allowed_users.set(allowed_user_ids or [])

            # Add related documents
            related_docs = request.POST.getlist('related_docs[]')
            if related_docs:
                register_doc.related_docs.set(related_docs)

            # Add approvers (optional)
            approvers = request.POST.getlist('approvers[]')
            approvers_count = 0
            if approvers:
                # Create DocumentApproval instances for each approver
                User = get_user_model()
                approvers_to_add = User.objects.filter(id__in=approvers)

                approval_objects = []
                for approver in approvers_to_add:
                    approval_objects.append(
                        DocumentApproval(
                            document=register_doc,
                            approver=approver,
                            document_hash=register_doc.document_hash,
                            status='pending'
                        )
                    )

                # Bulk create all approvals
                DocumentApproval.objects.bulk_create(approval_objects)
                approvers_count = len(approval_objects)

            # Parse document content if file is uploaded and parse option is selected
            parse_document = request.POST.get('parse_document') == 'true'
            page_by_page = request.POST.get('parse_page_by_page') == 'true'
            parsing_result = False
            
            if 'file_doc' in request.FILES and parse_document:
                # Parse document content using Google AI
                parsing_result = parse_document_with_google_ai(register_doc, page_by_page)
                
                if not parsing_result:
                    logger.warning(f"Document parsing failed for document {register_doc.id}")

            # Log success
            logger.info(
                f"Document {register_doc.id} created successfully by user {request.user.id} "
                f"with {approvers_count} approvers. Parsing: {parsing_result}, Page by page: {page_by_page}"
            )

            return JsonResponse({
                'success': True,
                'message': _('Document added successfully'),
                'id': register_doc.id,
                'parsing_success': parsing_result
            })

    except ValidationError as e:
        logger.warning(f"Validation error adding document: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error adding document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)




@login_required
@user_can_edit
def approve_document(request, doc_id):
    try:
        if request.method != 'POST':
            raise ValidationError('Invalid request method')

        document = RegisterDocs.objects.get(id=doc_id)
        # Додаткова перевірка прав на погодження
        if not check_approval_access(request.user, doc_id):
            return JsonResponse({
                'success': False,
                'error': _('You are not authorized to approve this document')
            }, status=403)

        data = json.loads(request.body)
        submitted_hash = data.get('document_hash')
        logger.debug(f"Approval request - Document ID: {doc_id}")
        logger.debug(f"Submitted hash: {submitted_hash}")
        logger.debug(f"Current document hash: {document.document_hash}")

        if not submitted_hash:
            raise ValidationError('Document hash is required')

        # Перевіряємо актуальний хеш документа
        current_hash = document.generate_hash()
        logger.debug(f"Generated hash: {current_hash}")

        # Для нового документа або документа без хешу просто встановлюємо поточний хеш
        if not document.document_hash:
            document.document_hash = current_hash
            document.save()
            logger.debug("Initial hash set for document")
        # Для існуючого документа перевіряємо зміни
        elif document.document_hash != current_hash:
            document.document_hash = current_hash
            document.save()
            logger.debug("Document hash updated due to changes")

        # Перевіряємо відповідність хешів тільки якщо документ вже мав погодження
        has_approvals = DocumentApproval.objects.filter(
            document=document,
            status='approved'
        ).exists()

        if has_approvals and submitted_hash != current_hash:
            logger.debug(
                f"Hash mismatch for previously approved document: submitted {submitted_hash} != current {current_hash}")
            return JsonResponse({
                'success': False,
                'error': _('Document has been modified. Please review the latest version before approving'),
                'current_hash': current_hash
            }, status=400)

        # Перевіряємо чи є записи про погоджувачів
        if not DocumentApproval.objects.filter(document=document).exists():
            # Якщо немає погоджувачів, додаємо поточного користувача
            DocumentApproval.objects.create(
                document=document,
                approver=request.user,
                document_hash=current_hash,
                status='pending'
            )
            logger.debug(f"Added first approver {request.user.id}")

        # Get all assigned approvers
        all_approvers = set(document.documentapproval_set.values_list('approver_id', flat=True))

        if request.user.id not in all_approvers:
            # Додаємо користувача як погоджувача
            DocumentApproval.objects.create(
                document=document,
                approver=request.user,
                document_hash=current_hash,
                status='pending'
            )
            all_approvers.add(request.user.id)
            logger.debug(f"Added user {request.user.id} as approver")

        # Update or create approval for current user
        approval, created = DocumentApproval.objects.get_or_create(
            document=document,
            approver=request.user,
            defaults={
                'document_hash': current_hash,
                'status': 'approved',
                'approved_at': timezone.now()
            }
        )

        # If approval already existed, update it
        if not created:
            approval.document_hash = current_hash
            approval.status = 'approved'
            approval.approved_at = timezone.now()
            approval.save()
            logger.debug("Existing approval updated")
        else:
            logger.debug("New approval created")

        # Get current approved approvers with valid hashes
        approved_approvers = set(document.documentapproval_set.filter(
            status='approved',
            document_hash=current_hash
        ).values_list('approver_id', flat=True))

        # Update document approval status (update_fields avoids RegisterDocs.save() recalculating
        # hash and potentially resetting approvals when hash is considered "changed")
        document.is_approved = all_approvers == approved_approvers
        document.save(update_fields=['is_approved'])

        logger.debug(f"Document approval status updated: {document.is_approved}")
        logger.debug(f"Approved approvers: {approved_approvers}")
        logger.debug(f"Required approvers: {all_approvers}")

        # Prepare response data
        approvals_details = []
        for approval in document.documentapproval_set.select_related('approver').all():
            approvals_details.append({
                'approver_name': approval.approver.get_full_name() or approval.approver.username,
                'status': approval.status,
                'approved_at': approval.approved_at.isoformat() if approval.approved_at else None,
                'is_current_user': approval.approver_id == request.user.id,
                'hash_valid': approval.document_hash == current_hash
            })

        return JsonResponse({
            'success': True,
            'message': _('Your approval has been recorded'),
            'hash': current_hash,
            'is_approved': document.is_approved,
            'approval_status': {
                'total_approvers': len(all_approvers),
                'approved_count': len(approved_approvers),
                'remaining_count': len(all_approvers - approved_approvers),
                'is_fully_approved': document.is_approved,
                'approvals': approvals_details
            }
        })

    except RegisterDocs.DoesNotExist:
        logger.error(f"Document {doc_id} not found")
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except ValidationError as e:
        logger.error(f"Validation error in document approval: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error approving document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def document_approvals(request, doc_id):
    try:
        document = RegisterDocs.objects.get(id=doc_id)
        current_language = get_language()[:2]

        # Використовуємо select_related для зменшення кількості запитів
        approvals = DocumentApproval.objects.filter(document=document).select_related(
            'approver',
            'approver__cabinet',
            'approver__cabinet__position',
            'approver__cabinet__department'
        ).order_by('approved_at')

        approvals_data = []
        for approval in approvals:
            if approval.approver:
                try:
                    cabinet_user = approval.approver.cabinet
                    position_data = None
                    department_data = None

                    if cabinet_user:
                        if cabinet_user.position:
                            position_data = {
                                'position_name_ua': cabinet_user.position.get_name('ua') or cabinet_user.position.get_name('uk'),
                                'position_name_en': cabinet_user.position.get_name('en'),
                                'position_name_ru': cabinet_user.position.get_name('ru')
                            }

                        if cabinet_user.department:
                            department_data = {
                                'department_name_ua': cabinet_user.department.get_name('ua') or cabinet_user.department.get_name('uk'),
                                'department_name_en': cabinet_user.department.get_name('en'),
                                'department_name_ru': cabinet_user.department.get_name('ru')
                            }

                    position_name = (cabinet_user.position.get_name() or '') if (cabinet_user and cabinet_user.position) else None
                    department_name = (cabinet_user.department.get_name() or '') if (cabinet_user and cabinet_user.department) else None
                    approver_data = {
                        'approver_id': approval.approver.id,
                        'approver_name': approval.approver.get_full_name() or approval.approver.username,
                        'position': position_data,
                        'position_name': position_name,
                        'department': department_data,
                        'department_name': department_name,
                        'approval_date': approval.approved_at.isoformat() if approval.approved_at else None,
                        'document_hash': approval.document_hash,
                        'status': approval.status,
                        'group': approval.approver.groups.first().name if approval.approver.groups.exists() else None
                    }
                    approvals_data.append(approver_data)
                    # print('document_approvals approver_data = ', approver_data)
                except Exception as e:
                    logger.error(f"Error processing approval data: {str(e)}", exc_info=True)
                    continue

        total_approvers = []
        for approval in approvals:
            if approval.approver:
                cabinet_user = approval.approver.cabinet
                position_data = None
                department_data = None

                if cabinet_user:
                    if cabinet_user.position:
                        position_data = {
                            'position_name_ua': cabinet_user.position.get_name('ua') or cabinet_user.position.get_name('uk'),
                            'position_name_en': cabinet_user.position.get_name('en'),
                            'position_name_ru': cabinet_user.position.get_name('ru')
                        }

                    if cabinet_user.department:
                        department_data = {
                            'department_name_ua': cabinet_user.department.get_name('ua') or cabinet_user.department.get_name('uk'),
                            'department_name_en': cabinet_user.department.get_name('en'),
                            'department_name_ru': cabinet_user.department.get_name('ru')
                        }

                position_name = (cabinet_user.position.get_name() or '') if (cabinet_user and cabinet_user.position) else None
                department_name = (cabinet_user.department.get_name() or '') if (cabinet_user and cabinet_user.department) else None
                total_approvers.append({
                    'approver_id': approval.approver.id,
                    'name': approval.approver.get_full_name() or approval.approver.username,
                    'status': approval.status,
                    'date': approval.approved_at.strftime('%Y-%m-%d %H:%M:%S') if approval.approved_at else None,
                    'position': position_data,
                    'position_name': position_name,
                    'department': department_data,
                    'department_name': department_name,
                    'email': approval.approver.email,
                    'group': approval.approver.groups.first().name if approval.approver.groups.exists() else None
                })
        # print('total_approvers', total_approvers)

        return JsonResponse({
            'success': True,
            'approvals': approvals_data,
            'document_hash': document.document_hash,
            'is_approved': document.is_approved,
            'total_approvers': total_approvers,
            'required_approvers_count': len(total_approvers),
            'approved_count': len([a for a in approvals_data if a['status'] == 'approved']),
            'current_user': {
                'id': request.user.id,
                'name': request.user.get_full_name() or request.user.username,
                'can_approve': request.user.id in [a.get('approver_id') for a in total_approvers]
            }
        })

    except RegisterDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.exception(f"Error getting approvals: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def acknowledge_document(request, doc_id):
    """Record that the current user has familiarized with the document (fixes document hash)."""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)
    try:
        document = RegisterDocs.objects.get(id=doc_id)
        if not document.has_access(request.user):
            return JsonResponse({
                'success': False,
                'error': _('You do not have access to this document')
            }, status=403)
        if not document.is_approved:
            return JsonResponse({
                'success': False,
                'error': _('Document must be fully approved by all approvers before you can acknowledge it.')
            }, status=400)
        try:
            current_hash = document.generate_hash()
        except Exception as hash_err:
            logger.warning(f"generate_hash failed for doc {doc_id}, using stored hash: {hash_err}")
            current_hash = (document.document_hash or '').strip()
        if not current_hash:
            current_hash = sha256(str(timezone.now().timestamp()).encode()).hexdigest()
        if not (document.document_hash or '').strip():
            document.document_hash = current_hash
            document.save(update_fields=['document_hash'])
        else:
            current_hash = (document.document_hash or '').strip() or current_hash
        now = timezone.now()
        fam, created = DocumentFamiliarization.objects.update_or_create(
            document=document,
            user=request.user,
            defaults={
                'document_hash': current_hash,
                'acknowledged_at': now,
            }
        )
        if not created:
            fam.acknowledged_at = now
            fam.document_hash = current_hash
            fam.save(update_fields=['acknowledged_at', 'document_hash'])
        return JsonResponse({
            'success': True,
            'message': _('Your familiarization has been recorded'),
            'document_hash': current_hash,
            'acknowledged_at': (fam.acknowledged_at or now).isoformat(),
        })
    except RegisterDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.exception(f"Error recording familiarization: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_can_edit
def delete_register_doc(request, doc_id):
    """View for deleting register document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            doc = RegisterDocs.objects.get(id=doc_id)

            # Delete the file if exists
            if doc.file_doc:
                doc.file_doc.delete(save=False)

            doc.delete()
            return JsonResponse({
                'success': True,
                'message': _('Document deleted successfully')
            })

    except RegisterDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)



def _format_allowed_user_for_doc(user):
    """Format a User (allowed_users) for JSON response in get_register_doc."""
    cabinet = getattr(user, 'cabinet', None)
    position_name = (cabinet.position.get_name() if cabinet and getattr(cabinet, 'position', None) else None) or None
    department_name = (cabinet.department.get_name() if cabinet and getattr(cabinet, 'department', None) else None) or None
    return {
        'id': user.id,
        'username': user.username,
        'full_name': user.get_full_name() or user.username,
        'email': user.email or '',
        'position_name': position_name,
        'department_name': department_name,
    }


@login_required
def get_register_doc(request, doc_id):
    try:
        doc = RegisterDocs.objects.select_related(
            'company', 'type_doc', 'status_doc', 'access_classification'
        ).get(id=doc_id)
        logger.debug(f"Found document: {doc}")
        logger.debug(f"File exists: {bool(doc.file_doc)}")

        file_data = _register_doc_file_metadata(doc, include_hash=False)
        if file_data is not None:
            logger.debug(f"File data: {file_data}")
        current_language = get_language()[:2]
        data = {
            'id': doc.id,
            'name_doc': doc.name_doc,
            'company': {
                'id': doc.company.id,
                'name': doc.company.name
            } if doc.company else None,
            'type_doc': {
                'id': doc.type_doc.id,
                'text': doc.type_doc.get_name() if doc.type_doc else '',
                'color': doc.type_doc.color
            } if doc.type_doc else None,
            'status_doc': {
                'id': doc.status_doc.id,
                'text': doc.status_doc.get_name(),
                'color': doc.status_doc.color
            } if doc.status_doc else None,
            'access_classification': {
                'id': doc.access_classification.id,
                'text': doc.access_classification.get_name(),
                'color': doc.access_classification.color,
                'icon': doc.access_classification.icon
            } if doc.access_classification else None,
            'vers_doc': doc.vers_doc,
            'date_doc': doc.date_doc.strftime('%Y-%m-%d'),
            'description': doc.description,
            'vers_doc_html': doc.vers_doc_html,
            'version_history': doc.version_history or '',
            'file_doc': file_data,  # Використовуємо підготовлений file_data
            'groups': list(doc.groups.values_list('id', flat=True)),
            'allowed_users': [
                _format_allowed_user_for_doc(u)
                for u in doc.allowed_users.prefetch_related('cabinet', 'cabinet__position', 'cabinet__department').all()
            ],
            'related_docs': list(doc.related_docs.values_list('id', flat=True)),
            'previous_version': doc.previous_version_id,

        }

        return JsonResponse({
            'success': True,
            'data': data
        })

    except Exception as e:
        logger.error(f"Error getting document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_can_edit
def edit_register_doc(request, doc_id):
    """Edit register document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            # Get document with select_related to minimize queries
            doc = RegisterDocs.objects.select_related(
                'company', 'type_doc', 'status_doc', 'access_classification', 'created_by', 'updated_by'
            ).get(id=doc_id)

            # Set current user for model's save method
            doc._current_user = request.user

            # Update main fields
            doc.name_doc = request.POST.get('name_doc')
            doc.company_id = request.POST.get('company')
            doc.type_doc_id = request.POST.get('type_doc')
            doc.status_doc_id = request.POST.get('status_doc')
            doc.vers_doc = request.POST.get('vers_doc')

            prev_version_id = request.POST.get('previous_version') or None
            if prev_version_id:
                try:
                    doc.previous_version_id = int(prev_version_id)
                except (TypeError, ValueError):
                    doc.previous_version_id = None
            else:
                doc.previous_version_id = None

            # Update access classification
            access_classification_id = request.POST.get('access_classification')
            if access_classification_id:
                try:
                    doc.access_classification = AccessClassification.objects.get(id=access_classification_id)
                except AccessClassification.DoesNotExist:
                    logger.warning(f'Invalid access classification ID: {access_classification_id}')
                    doc.access_classification = None
            else:
                doc.access_classification = None

            # Handle date field
            date_doc = request.POST.get('date_doc')
            if date_doc:
                try:
                    parsed_date = parse_date(date_doc)
                    if parsed_date:
                        doc.date_doc = parsed_date
                    else:
                        raise ValidationError(_('Invalid date format'))
                except ValueError:
                    raise ValidationError(_('Invalid date format'))

            doc.description = request.POST.get('description')

            # Handle version history
            doc.version_history = request.POST.get('version_history') or None

            # Handle HTML version
            if 'vers_doc_html' in request.POST:
                doc.vers_doc_html = request.POST.get('vers_doc_html')

            # Handle file operations
            remove_file = request.POST.get('remove_file') == 'true'
            if remove_file:
                # Save old file path for deletion
                old_file_path = doc.file_doc.path if doc.file_doc else None

                # Clear file field
                doc.file_doc = None
                doc.document_hash = None  # Clear hash when file is removed

                # Delete physical file after clearing the field
                if old_file_path and os.path.exists(old_file_path):
                    os.remove(old_file_path)

                logger.info(f"File removed from document {doc_id}")
            elif 'file_doc' in request.FILES:
                # Handle new file upload
                if doc.file_doc:
                    try:
                        # Save old file path
                        old_file_path = doc.file_doc.path
                        # Delete old file if it exists
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    except Exception as e:
                        logger.warning(f"Error deleting old file for document {doc_id}: {str(e)}")

                # Set new file
                doc.file_doc = request.FILES['file_doc']
                logger.info(f"New file uploaded for document {doc_id}")

            # Save document
            doc.save()

            # Update groups and allowed users (at least one required)
            groups = request.POST.getlist('groups[]')
            allowed_user_ids = request.POST.getlist('allowed_users[]')
            if not groups and not allowed_user_ids:
                raise ValidationError(_('Select at least one: Groups and/or Cabinet users.'))
            doc.groups.set(groups or [])
            doc.allowed_users.set(allowed_user_ids or [])

            # Update related documents
            related_docs = request.POST.getlist('related_docs[]')
            if related_docs:
                doc.related_docs.set(related_docs)
            else:
                doc.related_docs.clear()

            # Handle approvers (optional)
            approvers = request.POST.getlist('approvers[]')
            try:
                # Get existing approvals
                existing_approvals = {
                    str(approval.approver_id): approval
                    for approval in DocumentApproval.objects.filter(document=doc)
                }

                if approvers:
                    # Prepare new approvals
                    User = get_user_model()
                    approvers_to_add = User.objects.filter(id__in=approvers)

                    new_approvals = []
                    approvers_to_remove = set(existing_approvals.keys()) - set(approvers)

                    # Remove approvals for approvers that were removed
                    if approvers_to_remove:
                        DocumentApproval.objects.filter(
                            document=doc,
                            approver_id__in=approvers_to_remove
                        ).delete()

                    # Create or update approvals
                    for approver in approvers_to_add:
                        approver_id = str(approver.id)
                        if approver_id in existing_approvals:
                            # Keep existing approval if approver hasn't changed
                            existing_approval = existing_approvals[approver_id]
                            # Only update hash if document content changed
                            if doc.document_hash != existing_approval.document_hash:
                                existing_approval.document_hash = doc.document_hash
                                existing_approval.status = 'pending'  # Reset status if document changed
                                existing_approval.save()
                        else:
                            # Create new approval for new approver
                            new_approvals.append(
                                DocumentApproval(
                                    document=doc,
                                    approver=approver,
                                    document_hash=doc.document_hash,
                                    status='pending'
                                )
                            )

                    # Bulk create only new approvals
                    if new_approvals:
                        DocumentApproval.objects.bulk_create(new_approvals)
                else:
                    # If no approvers selected, remove all existing approvals
                    if existing_approvals:
                        DocumentApproval.objects.filter(document=doc).delete()

                # Update document approval status
                doc.is_approved = False  # Reset approval status when document is edited
                doc.save(update_fields=['is_approved'])

            except Exception as e:
                logger.error(f"Error updating approvers: {str(e)}")
                raise ValidationError(_('Error updating document approvers'))

            # Prepare response data
            updated_data = format_document_data(doc, get_language())

            logger.info(f"Document {doc.id} updated successfully by user {request.user.id}")

            return JsonResponse({
                'success': True,
                'message': _('Document updated successfully'),
                'data': updated_data
            })

    except RegisterDocs.DoesNotExist:
        logger.error(f"Document {doc_id} not found")
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except ValidationError as e:
        logger.error(f"Validation error updating document {doc_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating document {doc_id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': _('Error updating document')
        }, status=500)

@login_required
def get_reg_doc_html(request, doc_id):
    """Get HTML version of related document"""
    try:
        doc = RegisterDocs.objects.get(id=doc_id)
        if not doc.vers_doc_html:
            return JsonResponse({
                'success': False,
                'error': _('No HTML version available')
            }, status=404)

        return JsonResponse({
            'success': True,
            'data': {
                'html': doc.vers_doc_html
            }
        })

    except RegisterDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting HTML version: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
@login_required
def get_related_docs(request, doc_id):
    """View for getting related documents data"""
    try:
        # Get the main document
        doc = RegisterDocs.objects.get(id=doc_id)

        # Get related documents with their data
        related_docs = doc.related_docs.all()

        # Format the data for response
        data = [{
            'name_rel_doc': rel_doc.name_rel_doc,
            'company': rel_doc.company.name if rel_doc.company else None,
            'vers_rel_doc': rel_doc.vers_rel_doc,
            'date_rel_doc': rel_doc.date_rel_doc.strftime('%Y-%m-%d'),
            'file_rel_doc': rel_doc.file_rel_doc.url if rel_doc.file_rel_doc else None
        } for rel_doc in related_docs]

        return JsonResponse({
            'success': True,
            'data': data
        })

    except RegisterDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting related documents: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def format_related_doc_data(doc):
    """Format related document data for JSON response"""
    lang = get_language()[:2]
    
    access_classification_data = None
    if doc.access_classification:
        access_classification_data = {
            'id': doc.access_classification.id,
            'text': doc.access_classification.get_name(),
            'color': doc.access_classification.color,
            'icon': doc.access_classification.icon
        }
    
    return {
        'id': doc.id,
        'name_rel_doc': doc.name_rel_doc,
        'company': doc.company.name if doc.company else None,
        'vers_rel_doc': doc.vers_rel_doc,
        'date_rel_doc': doc.date_rel_doc.strftime('%Y-%m-%d'),
        'description_rel_doc': doc.description_rel_doc,
        'vers_rel_doc_html': bool(doc.vers_rel_doc_html),
        'file_rel_doc': doc.file_rel_doc.url if doc.file_rel_doc else None,
        'status_rel_doc': doc.status_rel_doc.get_name() if doc.status_rel_doc else None,
        'access_classification': access_classification_data,
        'groups': [group.name for group in doc.groups.all()]
    }


@login_required
@user_can_edit
def related_docs(request):
    """Main view for related documents page"""
    try:
        user_groups = request.user.groups.all()
        # Get companies that user can access based on AccessDocs settings
        allowed_companies = get_user_allowed_doc_companies(request.user)
        
        # Log for debugging
        logger.info(f"User {request.user.email} allowed companies for related_docs: {[c.name for c in allowed_companies]}")
        
        groups = Group.objects.all()
        current_language = request.LANGUAGE_CODE
        if len(current_language) == 2:  # If we have only language code (e.g., 'en')
            language_map = {
                'en': 'en-US',
                'uk': 'uk-UA',
                'ru': 'ru-RU'
            }
            current_language = language_map.get(current_language, 'en-US')

        # Get access classifications ordered by priority
        access_classifications = AccessClassification.objects.filter(is_active=True).order_by('sort_order', 'id')
        
        context = {
            'companies': allowed_companies,
            'current_language': current_language,
            'groups': groups,
            'doc_statuses': DocStatus.get_statuses_by_priority(),
            'access_classifications': access_classifications
        }
        return render(request, 'app_doc/related_docs.html', context)

    except Exception as e:
        logger.error(f"Error in related_docs view: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': _('Error loading page')
        }, status=500)


@login_required
def related_docs_list(request):
    """API endpoint for DataTables to get related documents list"""
    try:
        user_groups = request.user.groups.all()
        related_docs = RelatedDocs.objects.filter(groups__in=user_groups).distinct()
        
        # Order by status priority (sort_order), then by date and name
        related_docs = related_docs.order_by('status_rel_doc__sort_order', '-date_rel_doc', 'name_rel_doc')

        data = [format_related_doc_data(doc) for doc in related_docs]

        return JsonResponse({
            'draw': int(request.GET.get('draw', 1)),
            'recordsTotal': len(data),
            'recordsFiltered': len(data),
            'data': data
        })

    except Exception as e:
        logger.error(f"Error getting related documents list: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': _('Error loading documents')
        }, status=500)


@login_required
@user_can_edit
def add_related_doc(request):
    """Add new related document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            # Get AccessClassification instance if provided
            access_classification = None
            access_classification_id = request.POST.get('access_classification')
            if access_classification_id:
                try:
                    access_classification = AccessClassification.objects.get(id=access_classification_id)
                except AccessClassification.DoesNotExist:
                    logger.warning(f'Invalid access classification ID: {access_classification_id}')

            # Create new RelatedDocs instance
            related_doc = RelatedDocs(
                name_rel_doc=request.POST.get('name_rel_doc'),
                company_id=request.POST.get('company'),
                vers_rel_doc=request.POST.get('vers_rel_doc'),
                date_rel_doc=request.POST.get('date_rel_doc'),
                description_rel_doc=request.POST.get('description_rel_doc'),
                vers_rel_doc_html=request.POST.get('vers_rel_doc_html'),
                status_rel_doc_id=request.POST.get('status_rel_doc') if request.POST.get('status_rel_doc') else None,
                access_classification=access_classification
            )

            # Handle file upload
            if 'file_rel_doc' in request.FILES:
                related_doc.file_rel_doc = request.FILES['file_rel_doc']

            # Save the document
            related_doc.save()

            # Add groups
            groups = request.POST.getlist('groups[]')
            if groups:
                related_doc.groups.set(groups)
            else:
                return JsonResponse({
                    'success': False,
                    'error': _('At least one group must be selected')
                }, status=400)

            return JsonResponse({
                'success': True,
                'message': _('Document added successfully')
            })

    except Exception as e:
        logger.error(f"Error adding related document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_related_doc(request, doc_id):
    """Get related document data"""
    try:
        doc = RelatedDocs.objects.get(id=doc_id)
        data = {
            'id': doc.id,
            'name_rel_doc': doc.name_rel_doc,
            'company': doc.company.id if doc.company else None,
            'vers_rel_doc': doc.vers_rel_doc,
            'date_rel_doc': doc.date_rel_doc.strftime('%Y-%m-%d'),
            'description_rel_doc': doc.description_rel_doc,
            'vers_rel_doc_html': doc.vers_rel_doc_html,
            'file_rel_doc': doc.file_rel_doc.url if doc.file_rel_doc else None,
            'status_rel_doc': doc.status_rel_doc.id if doc.status_rel_doc else None,
            'access_classification': doc.access_classification.id if doc.access_classification else None,
            'groups': list(doc.groups.values_list('id', flat=True))
        }
        return JsonResponse({
            'success': True,
            'data': data
        })

    except ObjectDoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting related document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_can_edit
def edit_related_doc(request, doc_id):
    """Edit related document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            doc = RelatedDocs.objects.get(id=doc_id)

            # Update fields
            doc.name_rel_doc = request.POST.get('name_rel_doc')
            doc.company_id = request.POST.get('company')
            doc.vers_rel_doc = request.POST.get('vers_rel_doc')
            doc.date_rel_doc = request.POST.get('date_rel_doc')
            doc.description_rel_doc = request.POST.get('description_rel_doc')
            doc.status_rel_doc_id = request.POST.get('status_rel_doc') if request.POST.get('status_rel_doc') else None

            # Update access classification
            access_classification_id = request.POST.get('access_classification')
            if access_classification_id:
                try:
                    doc.access_classification = AccessClassification.objects.get(id=access_classification_id)
                except AccessClassification.DoesNotExist:
                    logger.warning(f'Invalid access classification ID: {access_classification_id}')
                    doc.access_classification = None
            else:
                doc.access_classification = None

            # Handle HTML version
            if 'vers_rel_doc_html' in request.POST:
                doc.vers_rel_doc_html = request.POST.get('vers_rel_doc_html')

            # Handle file upload
            if 'file_rel_doc' in request.FILES:
                # Delete old file if exists
                if doc.file_rel_doc:
                    doc.file_rel_doc.delete(save=False)
                doc.file_rel_doc = request.FILES['file_rel_doc']

            # Save changes
            doc.save()

            # Update groups
            groups = request.POST.getlist('groups[]')
            if groups:
                doc.groups.set(groups)
            else:
                return JsonResponse({
                    'success': False,
                    'error': _('At least one group must be selected')
                }, status=400)

            return JsonResponse({
                'success': True,
                'message': _('Document updated successfully')
            })

    except RelatedDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating related document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@user_can_edit
def delete_related_doc(request, doc_id):
    """Delete related document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            doc = RelatedDocs.objects.get(id=doc_id)

            # Delete file if exists
            if doc.file_rel_doc:
                doc.file_rel_doc.delete(save=False)

            # Delete document
            doc.delete()

            return JsonResponse({
                'success': True,
                'message': _('Document deleted successfully')
            })

    except RelatedDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting related document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def get_related_doc_html(request, doc_id):
    """Get HTML version of related document"""
    try:
        doc = RelatedDocs.objects.get(id=doc_id)
        if not doc.vers_rel_doc_html:
            return JsonResponse({
                'success': False,
                'error': _('No HTML version available')
            }, status=404)

        return JsonResponse({
            'success': True,
            'data': {
                'html': doc.vers_rel_doc_html
            }
        })

    except RelatedDocs.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting HTML version: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@file_access_required
def protected_file_download(request, doc_id):
    try:
        doc = request.accessed_document

        # Визначаємо, який тип документа
        if isinstance(doc, RelatedDocs):
            file_field = doc.file_rel_doc
        else:
            file_field = doc.file_doc

        if not file_field:
            raise Http404(_("No file attached"))

        # Отримуємо оригінальне ім'я файлу
        filename = request.GET.get('filename')
        if not filename:
            filename = os.path.basename(file_field.name)

        # Відкриваємо файл і створюємо відповідь
        response = FileResponse(
            file_field.open('rb'),
            content_type='application/octet-stream'
        )

        # Встановлюємо заголовки для завантаження
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{urllib.parse.quote(filename)}'
        response['Content-Length'] = file_field.size

        return response

    except Exception as e:
        logger.error(f"Error serving file {doc_id}: {str(e)}")
        raise Http404(_("Error serving file"))


@login_required
def get_company_cabinet_users(request):
    """Get CabinetUser records for a specific company."""
    try:
        company_id = request.GET.get('company_id')
        if not company_id:
            return JsonResponse({
                'success': False,
                'error': _('Company ID is required')
            }, status=400)

        # Check if user has access to this company (for documents)
        # Use get_user_allowed_doc_companies for document-related access
        allowed_companies = get_user_allowed_doc_companies(request.user)
        if allowed_companies:
            if isinstance(allowed_companies, list):
                company_ids = [company.id for company in allowed_companies]
                if int(company_id) not in company_ids:
                    return JsonResponse({
                        'success': False,
                        'error': _('Access denied to this company')
                    }, status=403)
            # If it's a QuerySet (all companies), no restriction needed

        # Get active CabinetUsers for the company: active user account and currently active employee (start/end date)
        today = timezone.now().date()
        active_employee_filter = (
            (Q(start_date__isnull=True) | Q(start_date__date__lte=today)) &
            (Q(end_date__isnull=True) | Q(end_date__date__gte=today))
        )
        cabinet_users = CabinetUser.objects.filter(
            company_id=company_id,
            user__is_active=True
        ).filter(active_employee_filter).select_related(
            'user',
            'position',
            'department'
        ).distinct()

        users_data = []
        for cu in cabinet_users:
            position_data = None
            if cu.position:
                position_data = {
                    'position_name_ua': cu.position.get_name('ua') or cu.position.get_name('uk'),
                    'position_name_en': cu.position.get_name('en'),
                    'position_name_ru': cu.position.get_name('ru')
                }

            department_data = None
            if cu.department:
                department_data = {
                    'department_name_ua': cu.department.get_name('ua') or cu.department.get_name('uk'),
                    'department_name_en': cu.department.get_name('en'),
                    'department_name_ru': cu.department.get_name('ru')
                }

            position_name = (cu.position.get_name() or '') if cu.position else None
            department_name = (cu.department.get_name() or '') if cu.department else None
            users_data.append({
                'id': cu.user.id,
                'username': cu.user.username,
                'full_name': cu.user.get_full_name() or cu.user.username,
                'position': position_data,
                'position_name': position_name,
                'position_id': cu.position_id,
                'department': department_data,
                'department_name': department_name,
                'department_id': cu.department_id,
                'email': cu.user.email,
                'is_active': True
            })
        # print('get_company_cabinet_users users_data = ',users_data )
        return JsonResponse({
            'success': True,
            'users': users_data
        })

    except Exception as e:
        logger.error(f"Error getting company cabinet users: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_company_groups(request):
    try:
        company_id = request.GET.get('company_id')
        if not company_id:
            return JsonResponse({
                'success': False,
                'error': _('Company ID is required')
            }, status=400)

        # Check if user has access to this company (for documents)
        allowed_companies = get_user_allowed_doc_companies(request.user)
        if allowed_companies:
            if isinstance(allowed_companies, list):
                company_ids = [company.id for company in allowed_companies]
                if int(company_id) not in company_ids:
                    return JsonResponse({
                        'success': False,
                        'error': _('Access denied to this company')
                    }, status=403)
            # If it's a QuerySet (all companies), no restriction needed

        cabinet_groups = CabinetGroup.objects.filter(
            company_id=company_id
        ).select_related('group')

        groups_data = [{
            'id': group.group.id,
            'name': group.name,
            'description': group.description or '',
            'color': group.color
        } for group in cabinet_groups]

        return JsonResponse({
            'success': True,
            'groups': groups_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def get_company_documents(request):
    """Get RegisterDocs for a specific company"""
    try:
        company_id = request.GET.get('company_id')
        if not company_id:
            return JsonResponse({
                'success': False,
                'error': _('Company ID is required')
            }, status=400)

        # Check if user has access to this company (for mandatory processes)
        allowed_companies = get_user_allowed_companies(request.user)
        if allowed_companies:
            if isinstance(allowed_companies, list):
                company_ids = [company.id for company in allowed_companies]
                if int(company_id) not in company_ids:
                    return JsonResponse({
                        'success': False,
                        'error': _('Access denied to this company')
                    }, status=403)
            # If it's a QuerySet (all companies), no restriction needed

        # Get user's groups for access control
        user_groups = request.user.groups.all()
        
        # Filter documents by company, user's group access, and Active status only
        documents = RegisterDocs.objects.filter(
            company_id=company_id,
            groups__in=user_groups,
            is_active=True,
            status_doc__code__iexact='active'
        ).distinct().select_related('status_doc').order_by('name_doc')

        documents_data = [{
            'id': doc.id,
            'name_doc': doc.name_doc,
            'vers_doc': doc.vers_doc,
            'date_doc': doc.date_doc.strftime('%Y-%m-%d') if doc.date_doc else '',
            'type_doc': doc.type_doc.get_name() if doc.type_doc else ''
        } for doc in documents]

        return JsonResponse({
            'success': True,
            'documents': documents_data
        })

    except Exception as e:
        logger.error(f"Error getting company documents: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_company_related_docs(request):
    """Get RelatedDocs for a specific company"""
    try:
        company_id = request.GET.get('company_id')
        if not company_id:
            return JsonResponse({
                'success': False,
                'error': _('Company ID is required')
            }, status=400)

        # Check if user has access to this company (for documents)
        allowed_companies = get_user_allowed_doc_companies(request.user)
        if allowed_companies:
            if isinstance(allowed_companies, list):
                company_ids = [company.id for company in allowed_companies]
                if int(company_id) not in company_ids:
                    return JsonResponse({
                        'success': False,
                        'error': _('Access denied to this company')
                    }, status=403)
            # If it's a QuerySet (all companies), no restriction needed

        # Get user's groups for access control
        user_groups = request.user.groups.all()
        
        # Filter related documents by company and user's group access
        related_docs = RelatedDocs.objects.filter(
            company_id=company_id,
            groups__in=user_groups
        ).distinct().order_by('status_rel_doc__sort_order', '-date_rel_doc', 'name_rel_doc')

        # Format data using existing function
        docs_data = [format_related_doc_data(doc) for doc in related_docs]

        return JsonResponse({
            'success': True,
            'related_docs': docs_data
        })

    except Exception as e:
        logger.error(f"Error getting company related documents: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_company_register_docs(request):
    """Get RegisterDocs for a company (for Previous Document dropdown). Same access as reg_docs."""
    try:
        company_id = request.GET.get('company_id')
        if not company_id:
            return JsonResponse({
                'success': False,
                'error': _('Company ID is required')
            }, status=400)

        allowed_companies = get_user_allowed_doc_companies(request.user)
        if allowed_companies:
            if isinstance(allowed_companies, list):
                company_ids = [c.id for c in allowed_companies]
                if int(company_id) not in company_ids:
                    return JsonResponse({
                        'success': False,
                        'error': _('Access denied to this company')
                    }, status=403)

        user_groups = request.user.groups.all()
        qs = RegisterDocs.objects.filter(
            company_id=company_id,
            is_active=True
        ).filter(
            Q(groups__in=user_groups) | Q(allowed_users=request.user)
        ).distinct().select_related('status_doc').order_by('-date_doc', 'name_doc')

        exclude_doc_id = request.GET.get('exclude_doc_id')
        if exclude_doc_id:
            qs = qs.exclude(id=int(exclude_doc_id))

        documents_data = [{
            'id': doc.id,
            'name_doc': doc.name_doc,
            'status_doc': doc.status_doc.get_name() if doc.status_doc else '',
            'date_doc': doc.date_doc.strftime('%Y-%m-%d') if doc.date_doc else '',
            'vers_doc': doc.vers_doc,
        } for doc in qs]

        return JsonResponse({
            'success': True,
            'documents': documents_data
        })

    except Exception as e:
        logger.error(f"Error getting company register docs: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def legislative_docs(request):
    try:
        user_access = get_legislative_user_access_level(request.user)
        if not user_access['has_access']:
            return JsonResponse({
                'success': False,
                'error': _('Access denied')
            }, status=403)

        user_groups = request.user.groups.all()
        
        # Handle AJAX request for DataTables
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if request.GET.get('action') == 'get_company_users':
                return handle_company_users_request(request)
            elif request.GET.get('action') == 'get_regulators':
                return get_regulators(request)

            # Handle DataTables AJAX request
            try:
                start = int(request.GET.get('start', 0))
                length = int(request.GET.get('length', 25))
                draw = int(request.GET.get('draw', 1))

                # Get documents accessible to the user's groups
                legislative_docs = LegislativeDoc.objects.filter(
                    groups__in=user_groups
                ).prefetch_related('company').select_related('doc_type', 'regulator').distinct()
                
                # Get total record count
                total = legislative_docs.count()

                # Handle search
                search_value = request.GET.get('search[value]', '')
                if search_value:
                    legislative_docs = legislative_docs.filter(
                        Q(title__icontains=search_value) |
                        Q(doc_number__icontains=search_value) |
                        Q(issuing_authority__icontains=search_value) |
                        Q(description__icontains=search_value)
                    )
                
                # Handle advanced search parameters
                title_filter = request.GET.get('title', '')
                if title_filter:
                    legislative_docs = legislative_docs.filter(title__icontains=title_filter)
                
                doc_number_filter = request.GET.get('doc_number', '')
                if doc_number_filter:
                    legislative_docs = legislative_docs.filter(doc_number__icontains=doc_number_filter)
                
                doc_type_filter = request.GET.get('doc_type', '')
                if doc_type_filter:
                    legislative_docs = legislative_docs.filter(doc_type_id=doc_type_filter)
                
                regulator_filter = request.GET.get('regulator', '')
                if regulator_filter:
                    legislative_docs = legislative_docs.filter(regulator_id=regulator_filter)
                
                company_filter = request.GET.get('company', '')
                if company_filter:
                    legislative_docs = legislative_docs.filter(company=company_filter)
                
                start_date_filter = request.GET.get('start_date', '')
                if start_date_filter:
                    # First try to filter by effective date, then by issue date
                    legislative_docs = legislative_docs.filter(
                        Q(effective_date__gte=start_date_filter) | 
                        Q(effective_date__isnull=True, issue_date__gte=start_date_filter)
                    )
                
                end_date_filter = request.GET.get('end_date', '')
                if end_date_filter:
                    # First try to filter by effective date, then by issue date
                    legislative_docs = legislative_docs.filter(
                        Q(effective_date__lte=end_date_filter) | 
                        Q(effective_date__isnull=True, issue_date__lte=end_date_filter)
                    )
                
                # Search in HTML content
                html_content_filter = request.GET.get('html_content', '')
                if html_content_filter:
                    legislative_docs = legislative_docs.filter(html_content__icontains=html_content_filter)

                # Get filtered count
                filtered_total = legislative_docs.count()

                # Order
                order_column = int(request.GET.get('order[0][column]', 0))
                order_dir = request.GET.get('order[0][dir]', 'asc')

                # Map column index to field name
                order_columns = ['title', 'doc_number', 'doc_type', 'issuing_authority', 'issue_date', 'effective_date']
                if order_column < len(order_columns):
                    order_field = order_columns[order_column]
                    if order_dir == 'desc':
                        order_field = f'-{order_field}'
                    legislative_docs = legislative_docs.order_by(order_field)

                # Apply pagination
                legislative_docs = legislative_docs[start:start + length]

                # Format data
                docs_data = []
                for doc in legislative_docs:
                    docs_data.append({
                        'id': doc.id,
                        'title': doc.title,
                        'doc_number': doc.doc_number,
                        'doc_type': doc.doc_type.get_name() if doc.doc_type else _("Not specified"),
                        'doc_type_color': doc.doc_type.color if doc.doc_type else None,
                        'issuing_authority': doc.issuing_authority,
                        'regulator': {
                            'id': doc.regulator.id,
                            'name': doc.regulator.name,
                            'code': doc.regulator.code,
                            'color': doc.regulator.color,
                            'website': doc.regulator.website
                        } if doc.regulator else None,
                        'original_url': doc.original_url,
                        'issue_date': doc.issue_date.strftime('%Y-%m-%d') if doc.issue_date else None,
                        'effective_date': doc.effective_date.strftime('%Y-%m-%d') if doc.effective_date else None,
                        'expiration_date': doc.expiration_date.strftime('%Y-%m-%d') if doc.expiration_date else None,
                        'description': doc.description,
                        'has_pdf': bool(doc.pdf_file),
                        'has_html': bool(doc.html_content),
                        'company': ', '.join([c.name for c in doc.company.all()]) if doc.company.exists() else None,
                        'companies': [{'id': c.id, 'name': c.name} for c in doc.company.all()],
                        'created_at': doc.created_at.strftime('%Y-%m-%d'),
                        'updated_at': doc.updated_at.strftime('%Y-%m-%d'),
                        'created_by': doc.created_by.get_full_name() if doc.created_by else None,
                        'can_edit': user_access['can_edit']
                    })

                return JsonResponse({
                    'draw': draw,
                    'recordsTotal': total,
                    'recordsFiltered': filtered_total,
                    'data': docs_data
                })

            except Exception as e:
                logger.error(f"Error processing DataTables request: {str(e)}", exc_info=True)
                return JsonResponse({
                    'error': str(e)
                }, status=500)

        # Regular page load context
        cabinet_groups = CabinetGroup.objects.select_related('group').all()
        regulators = RegulatorName.objects.filter(is_active=True).order_by('name')
        doc_types = DocType.objects.filter(is_active=True).order_by('name', 'name_local')
        
        # Get companies that user can access based on AccessDocs settings
        allowed_companies = get_user_allowed_doc_companies(request.user)
        
        context = {
            'companies': allowed_companies,
            'groups': cabinet_groups,
            'regulators': regulators,
            'doc_types': doc_types,
            'user_access': user_access,
            'current_language': get_language(),
        }
        return render(request, 'app_doc/legislative_docs.html', context)

    except Exception as e:
        logger.error(f"Error in legislative_docs view: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
def get_regulators(request):
    """Get list of regulators for AJAX requests"""
    try:
        regulators = RegulatorName.objects.filter(is_active=True).order_by('name')
        
        data = [{
            'id': reg.id,
            'name': reg.name,
            'code': reg.code,
            'description': reg.description,
            'color': reg.color,
            'website': reg.website
        } for reg in regulators]
        
        return JsonResponse({
            'success': True,
            'regulators': data
        })
    except Exception as e:
        logger.error(f"Error getting regulators: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@user_can_edit
def add_legislative_doc(request):
    """View for adding new legislative document"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Invalid request method')
        }, status=405)

    try:
        with transaction.atomic():
            # Get DocType instance
            doc_type_id = request.POST.get('doc_type')
            doc_type = None
            if doc_type_id:
                try:
                    doc_type = DocType.objects.get(id=doc_type_id)
                except DocType.DoesNotExist:
                    raise ValidationError(_('Invalid document type'))
            
            # Create new LegislativeDoc instance
            legislative_doc = LegislativeDoc(
                title=request.POST.get('title'),
                doc_number=request.POST.get('doc_number'),
                doc_type=doc_type,
                issuing_authority=request.POST.get('issuing_authority'),
                original_url=request.POST.get('original_url'),
                description=request.POST.get('description'),
                html_content=request.POST.get('html_content'),
                created_by=request.user,
                updated_by=request.user
            )
            
            # Handle regulator selection
            regulator_id = request.POST.get('regulator')
            if regulator_id:
                legislative_doc.regulator_id = regulator_id
            
            # Handle dates
            issue_date = request.POST.get('issue_date')
            if issue_date:
                legislative_doc.issue_date = issue_date
                
            effective_date = request.POST.get('effective_date')
            if effective_date:
                legislative_doc.effective_date = effective_date
                
            expiration_date = request.POST.get('expiration_date')
            if expiration_date:
                legislative_doc.expiration_date = expiration_date

            # Handle file upload
            if 'pdf_file' in request.FILES:
                legislative_doc.pdf_file = request.FILES['pdf_file']

            # Save the document
            legislative_doc.save()

            # Add companies (multiple selection)
            companies = request.POST.getlist('company[]')
            if companies:
                legislative_doc.company.set(companies)

            # Add groups
            groups = request.POST.getlist('groups[]')
            if not groups:
                raise ValidationError(_('At least one group must be selected'))
            legislative_doc.groups.set(groups)

            # Parse document content if file is uploaded and parse option is selected
            parse_document = request.POST.get('parse_document') == 'true'
            
            if 'pdf_file' in request.FILES and parse_document:
                try:
                    # Here you would implement the pdf parsing functionality
                    # This is a placeholder for actual implementation
                    # For now, we'll just log that parsing was requested
                    logger.info(f"Document parsing requested for legislative document {legislative_doc.id}")
                except Exception as e:
                    logger.error(f"Error parsing document content: {str(e)}", exc_info=True)

            # Check if it's an AJAX request
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Add a success message
            messages.success(request, _('Legislative document added successfully'))
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': _('Legislative document added successfully'),
                    'id': legislative_doc.id
                })
            else:
                # For regular form submissions, redirect to the legislative docs page
                return HttpResponseRedirect(reverse('legislative_docs'))

    except ValidationError as e:
        logger.warning(f"Validation error adding legislative document: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        else:
            messages.error(request, str(e))
            return HttpResponseRedirect(reverse('legislative_docs'))
    except Exception as e:
        logger.error(f"Error adding legislative document: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        else:
            messages.error(request, _('Error adding legislative document'))
            return HttpResponseRedirect(reverse('legislative_docs'))

@login_required
def get_legislative_doc(request, doc_id):
    """Get legislative document data"""
    try:
        doc = LegislativeDoc.objects.select_related('regulator').prefetch_related('company').get(id=doc_id)
        
        # Check access
        if not doc.has_access(request.user):
            return JsonResponse({
                'success': False,
                'error': _('Access denied')
            }, status=403)
            
        # Prepare file data
        file_data = None
        if doc.pdf_file:
            file_data = {
                'url': doc.pdf_file.url,
                'name': os.path.basename(doc.pdf_file.name),
                'size': doc.pdf_file.size,
                'exists': True
            }
            
        # Prepare regulator data
        regulator_data = None
        if doc.regulator:
            regulator_data = {
                'id': doc.regulator.id,
                'name': doc.regulator.name,
                'code': doc.regulator.code,
                'color': doc.regulator.color,
                'website': doc.regulator.website
            }
            
        # Prepare doc_type data
        doc_type_data = None
        if doc.doc_type:
            doc_type_data = {
                'id': doc.doc_type.id,
                'name': doc.doc_type.get_name(),
                'color': doc.doc_type.color
            }
            
        data = {
            'id': doc.id,
            'title': doc.title,
            'doc_number': doc.doc_number,
            'doc_type': doc_type_data,
            'doc_type_id': doc.doc_type.id if doc.doc_type else None,
            'issuing_authority': doc.issuing_authority,
            'regulator': regulator_data,
            'regulator_id': doc.regulator_id,
            'original_url': doc.original_url,
            'issue_date': doc.issue_date.strftime('%Y-%m-%d') if doc.issue_date else None,
            'effective_date': doc.effective_date.strftime('%Y-%m-%d') if doc.effective_date else None,
            'expiration_date': doc.expiration_date.strftime('%Y-%m-%d') if doc.expiration_date else None,
            'description': doc.description,
            'pdf_file': file_data,
            'html_content': doc.html_content,
            'company': list(doc.company.values_list('id', flat=True)),
            'groups': list(doc.groups.values_list('id', flat=True))
        }

        return JsonResponse({
            'success': True,
            'data': data
        })

    except LegislativeDoc.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting legislative document: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@user_can_edit
def edit_legislative_doc(request, doc_id):
    """View for editing legislative document"""
    try:
        doc = LegislativeDoc.objects.get(id=doc_id)
        
        # Ensure user has edit permissions
        if not doc.can_edit(request.user):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': _('Access denied')
                }, status=403)
            else:
                messages.error(request, _('Access denied'))
                return HttpResponseRedirect(reverse('legislative_docs'))
        
        if request.method != 'POST':
            return JsonResponse({
                'success': False,
                'error': _('Invalid request method')
            }, status=405)
        
        with transaction.atomic():
            # Update fields
            doc.title = request.POST.get('title')
            doc.doc_number = request.POST.get('doc_number')
            
            # Handle document type
            doc_type_id = request.POST.get('doc_type')
            if doc_type_id:
                try:
                    doc.doc_type = DocType.objects.get(id=doc_type_id)
                except DocType.DoesNotExist:
                    raise ValidationError(_('Invalid document type'))
            else:
                doc.doc_type = None
                
            doc.issuing_authority = request.POST.get('issuing_authority')
            doc.original_url = request.POST.get('original_url')
            doc.description = request.POST.get('description')
            doc.html_content = request.POST.get('html_content')
            doc.updated_by = request.user
            
            # Handle regulator selection
            regulator_id = request.POST.get('regulator')
            if regulator_id:
                doc.regulator_id = regulator_id
            else:
                doc.regulator = None
                
            # Handle company selection (multiple)
            companies = request.POST.getlist('company[]')
            doc.company.set(companies) if companies else doc.company.clear()
            
            # Handle dates
            issue_date = request.POST.get('issue_date')
            doc.issue_date = issue_date if issue_date else None
                
            effective_date = request.POST.get('effective_date')
            doc.effective_date = effective_date if effective_date else None
                
            expiration_date = request.POST.get('expiration_date')
            doc.expiration_date = expiration_date if expiration_date else None
            
            # Handle file upload
            if 'pdf_file' in request.FILES:
                # Remove old file if it exists
                if doc.pdf_file:
                    old_file_path = doc.pdf_file.path
                    # Delete old file from storage
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                # Upload new file
                doc.pdf_file = request.FILES['pdf_file']
            
            # Handle file removal
            if request.POST.get('remove_file') == 'true' and doc.pdf_file:
                # Get path before setting to None
                old_file_path = doc.pdf_file.path
                # Set file to None in model
                doc.pdf_file = None
                # Delete file from storage
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            
            # Save the document
            doc.save()
            
            # Update groups
            groups = request.POST.getlist('groups[]')
            if not groups:
                raise ValidationError(_('At least one group must be selected'))
            doc.groups.set(groups)
            
            # Check if it's an AJAX request
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Add a success message
            messages.success(request, _('Legislative document updated successfully'))
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': _('Legislative document updated successfully'),
                    'id': doc.id
                })
            else:
                # For regular form submissions, redirect to the legislative docs page
                return HttpResponseRedirect(reverse('legislative_docs'))
        
    except LegislativeDoc.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': _('Document not found')
            }, status=404)
        else:
            messages.error(request, _('Document not found'))
            return HttpResponseRedirect(reverse('legislative_docs'))
    except ValidationError as e:
        logger.warning(f"Validation error editing legislative document {doc_id}: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        else:
            messages.error(request, str(e))
            return HttpResponseRedirect(reverse('legislative_docs'))
    except Exception as e:
        logger.error(f"Error editing legislative document {doc_id}: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        else:
            messages.error(request, _('Error updating legislative document'))
            return HttpResponseRedirect(reverse('legislative_docs'))

@login_required
@user_can_edit
def delete_legislative_doc(request, doc_id):
    """View for deleting legislative document"""
    try:
        doc = LegislativeDoc.objects.get(id=doc_id)
        
        # Ensure user has edit permissions
        if not doc.can_edit(request.user):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': _('Access denied')
                }, status=403)
            else:
                messages.error(request, _('Access denied'))
                return HttpResponseRedirect(reverse('legislative_docs'))
        
        if request.method != 'POST':
            return JsonResponse({
                'success': False,
                'error': _('Invalid request method')
            }, status=405)
        
        # Get file path before deletion (for file cleanup)
        pdf_file_path = None
        if doc.pdf_file:
            pdf_file_path = doc.pdf_file.path
        
        # Store the document title for the response
        doc_title = doc.title
        
        # Delete the document
        doc.delete()
        
        # Delete file from storage if it exists
        if pdf_file_path and os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Add a success message
        messages.success(request, _('Legislative document "%(title)s" deleted successfully') % {'title': doc_title})
        
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': _('Legislative document deleted successfully')
            })
        else:
            # For regular form submissions, redirect to the legislative docs page
            return HttpResponseRedirect(reverse('legislative_docs'))
        
    except LegislativeDoc.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': _('Document not found')
            }, status=404)
        else:
            messages.error(request, _('Document not found'))
            return HttpResponseRedirect(reverse('legislative_docs'))
    except Exception as e:
        logger.error(f"Error deleting legislative document {doc_id}: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        else:
            messages.error(request, _('Error deleting legislative document'))
            return HttpResponseRedirect(reverse('legislative_docs'))

@login_required
def get_legislative_doc_html(request, doc_id):
    """Get HTML content of legislative document"""
    try:
        doc = LegislativeDoc.objects.get(id=doc_id)
        
        # Check access
        if not doc.has_access(request.user):
            return JsonResponse({
                'success': False,
                'error': _('Access denied')
            }, status=403)
            
        if not doc.html_content:
            return JsonResponse({
                'success': False,
                'error': _('No HTML content available')
            }, status=404)

        return JsonResponse({
            'success': True,
            'data': {
                'title': doc.title,
                'html': doc.html_content
            }
        })

    except LegislativeDoc.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting HTML content: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def download_legislative_doc_pdf(request, doc_id):
    """Download PDF file of legislative document"""
    try:
        doc = LegislativeDoc.objects.get(id=doc_id)
        
        # Check access
        if not doc.has_access(request.user):
            return JsonResponse({
                'success': False,
                'error': _('Access denied')
            }, status=403)
            
        if not doc.pdf_file:
            return JsonResponse({
                'success': False,
                'error': _('No PDF file available')
            }, status=404)

        # Get original file name
        filename = os.path.basename(doc.pdf_file.name)

        # Open file and create response
        response = FileResponse(
            doc.pdf_file.open('rb'),
            content_type='application/pdf'
        )

        # Set headers for download
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{urllib.parse.quote(filename)}'
        response['Content-Length'] = doc.pdf_file.size

        return response

    except LegislativeDoc.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Document not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error downloading PDF: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def parse_document_ai(request):
    """Parse document using AI to identify mandatory processes"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': _('Only POST method allowed')
        }, status=405)
    
    try:
        document_id = request.POST.get('document_id')
        ai_provider = request.POST.get('ai_provider', 'gpt-4')
        ai_query = request.POST.get('ai_query', '')
        
        if not document_id:
            return JsonResponse({
                'success': False,
                'error': _('Document ID is required')
            }, status=400)
        
        # Get the document
        try:
            doc = RegisterDocs.objects.get(id=document_id)
        except RegisterDocs.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': _('Document not found')
            }, status=404)
        
        # Check if user has access to the document
        if not doc.has_access(request.user):
            return JsonResponse({
                'success': False,
                'error': _('Access denied to this document')
            }, status=403)
        
        # Check if document has a file
        if not doc.file_doc:
            return JsonResponse({
                'success': False,
                'error': _('Document has no file attached')
            }, status=400)
        
        # Use the new AI parsing function
        try:
            # Get current language from request
            current_language = getattr(request, 'LANGUAGE_CODE', 'en')
            
            ai_results = parse_document_with_ai(
                doc.file_doc.path,
                ai_query,
                ai_provider,
                current_language
            )
            
            # Process AI results to extract mandatory processes
            processes = []
            if ai_results.get('success') and 'processes' in ai_results:
                for process_data in ai_results['processes']:
                    processes.append({
                        'process_name': process_data.get('name', ''),
                        'description': process_data.get('description', ''),
                        'frequency': process_data.get('frequency', ''),
                        'source_document_section': process_data.get('section', '')
                    })
            
            # If no specific processes found, create a general one
            if not processes:
                processes.append({
                    'process_name': f"Process from {doc.name_doc}",
                    'description': ai_results.get('summary', 'Document analysis completed'),
                    'frequency': 'monthly',  # Default frequency
                    'source_document_section': 'General document content'
                })
            
            return JsonResponse({
                'success': True,
                'results': processes,
                'document_name': doc.name_doc,
                'ai_provider': ai_provider
            })
            
        except Exception as ai_error:
            logger.error(f"AI parsing error: {str(ai_error)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': _('AI analysis failed: ') + str(ai_error)
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in parse_document_ai: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def get_ai_models(request):
    """Get available AI models for each provider"""
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': _('Only GET method allowed')
        }, status=405)
    
    try:
        # Get current language from request
        current_language = getattr(request, 'LANGUAGE_CODE', 'en')
        
        # Get all active models grouped by provider
        models = ModelChoice.objects.filter(is_active=True).order_by('provider', 'model_name')
        
        models_by_provider = {}
        for model in models:
            provider = model.provider
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            
            models_by_provider[provider].append({
                'id': model.id,
                'model_id': model.model_id,
                'model_name': model.model_name,
                'provider': provider
            })
        
        # Create localized provider names
        provider_names = {
            'uk': {
                'claude': 'Claude',
                'google': 'Google',
                'groq': 'Groq',
                'deepseek': 'DeepSeek'
            },
            'ru': {
                'claude': 'Claude',
                'google': 'Google',
                'groq': 'Groq',
                'deepseek': 'DeepSeek'
            },
            'en': {
                'claude': 'Claude',
                'google': 'Google',
                'groq': 'Groq',
                'deepseek': 'DeepSeek'
            }
        }
        
        # Format response with localized names
        formatted_models = {}
        for provider, models_list in models_by_provider.items():
            provider_name = provider_names.get(current_language, provider_names['en']).get(provider, provider.title())
            formatted_models[provider] = {
                'provider_name': provider_name,
                'models': models_list
            }
        
        return JsonResponse({
            'success': True,
            'models': formatted_models,
            'language': current_language
        })
        
    except Exception as e:
        logger.error(f"Error in get_ai_models: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': _('Failed to retrieve AI models')
        }, status=500)


@login_required
def check_ai_settings_version(request):
    """Check if AI settings have changed by returning a version hash"""
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': _('Only GET method allowed')
        }, status=405)
    
    try:
        from hashlib import md5
        import json
        
        # Get all AI settings and create a hash
        ai_settings_data = {}
        
        # Get Claude settings
        from app_ai.models import APISettingsClaude
        claude_settings = APISettingsClaude.objects.first()
        if claude_settings:
            ai_settings_data['claude'] = {
                'model_id': claude_settings.model_name.model_id if claude_settings.model_name else None,
                'updated_at': claude_settings.updated_at.isoformat() if hasattr(claude_settings, 'updated_at') else None
            }
        
        # Get Google settings
        from app_ai.models import APISettingsGoogle
        google_settings = APISettingsGoogle.objects.first()
        if google_settings:
            ai_settings_data['google'] = {
                'model_id': google_settings.model_name.model_id if google_settings.model_name else None,
                'updated_at': google_settings.updated_at.isoformat() if hasattr(google_settings, 'updated_at') else None
            }
        
        # Get Groq settings
        from app_ai.models import APISettingsGroq
        groq_settings = APISettingsGroq.objects.first()
        if groq_settings:
            ai_settings_data['groq'] = {
                'model_id': groq_settings.model_name.model_id if groq_settings.model_name else None,
                'updated_at': groq_settings.updated_at.isoformat() if hasattr(groq_settings, 'updated_at') else None
            }
        
        # Get DeepSeek settings
        from app_ai.models import APISettingsDeepSeek
        deepseek_settings = APISettingsDeepSeek.objects.first()
        if deepseek_settings:
            ai_settings_data['deepseek'] = {
                'model_id': deepseek_settings.model_name.model_id if deepseek_settings.model_name else None,
                'updated_at': deepseek_settings.updated_at.isoformat() if hasattr(deepseek_settings, 'updated_at') else None
            }
        
        # Create a hash of the settings
        settings_json = json.dumps(ai_settings_data, sort_keys=True)
        settings_hash = md5(settings_json.encode()).hexdigest()
        
        return JsonResponse({
            'success': True,
            'version_hash': settings_hash,
            'settings': ai_settings_data
        })
        
    except Exception as e:
        logger.error(f"Error in check_ai_settings_version: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': _('Failed to check AI settings version')
        }, status=500)