import pytz
import json
import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from .models import AccessRisk, RiskReportGuide, RiskReportGuideTranslation
from .vulnerability_views import *
from .risk_assessment_views import *
from .threat_views import *
from .ai_views import *
from .report_views import get_user_companies, get_available_formats
from .access_utils import has_risk_report_access, get_user_risk_permissions, can_add_risk_report, can_edit_risk_report, can_delete_risk_report
from app_conf.models import Country
from django.shortcuts import render
from django.utils.translation import get_language, gettext as _
from datetime import datetime
from django import template
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from .models import ReportProfile
import json



logger = logging.getLogger(__name__)


logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")


def get_company_name_by_id(company_id):
    """Get company name by ID, return 'All Companies' if None or not found"""
    if not company_id:
        return 'All Companies'
    
    try:
        from app_cabinet.models import Company
        company = Company.objects.get(id=company_id)
        return company.name
    except Company.DoesNotExist:
        return 'All Companies'
    except Exception:
        return 'All Companies'



#
# register = template.Library()
#
#
# @register.filter
# def access_risk_assessment_show_link(groups):
#     return AccessRiskAssessment.objects.filter(group__in=groups, show_link=True).exists()



def get_server_time(request):
    user_timezone = request.session.get('user_timezone', 'UTC')
    server_time = timezone.now().astimezone(pytz.timezone(user_timezone))
    formatted_time = server_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    return JsonResponse({'server_time': formatted_time})

@require_POST
@login_required
@csrf_protect
def set_user_timezone(request):
    timezone = request.POST.get('timezone')
    if timezone:
        request.session['user_timezone'] = timezone
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
@user_passes_test(has_risk_report_access)
def risk_report(request):
    """Risk Report page with report generation and preview functionality"""
    try:
        
        # Get user's companies for filtering
        user_companies = get_user_companies(request.user)
        logger.info(f"User {request.user.username} has access to {user_companies.count()} companies: {[c.name for c in user_companies]}")
        
        # Get available report formats
        available_formats = get_available_formats()
        
        # Get current language
        current_language = get_language()[:2]
        
        # Get user permissions for the template
        user_permissions = get_user_risk_permissions(request.user)
        
        # Convert permissions to JSON-serializable format
        user_permissions_json = {
            'can_add_report': user_permissions['can_add_report'],
            'can_edit_report': user_permissions['can_edit_report'],
            'can_delete_report': user_permissions['can_delete_report'],
            'has_access_report': user_permissions['has_access_report'],
        }
        
        # Get available AI models for AI Conclusion
        from app_ai.models import ModelChoice
        ai_models = ModelChoice.objects.filter(is_active=True).order_by('provider', 'model_name')
        ai_models_list = [{'id': model.id, 'provider': model.provider, 'model_id': model.model_id, 'model_name': model.model_name} for model in ai_models]
        
        context = {
            'companies': user_companies,
            'available_formats': available_formats,
            'current_language': current_language,
            'page_title': 'Risk Report',
            'user_permissions': user_permissions,
            'user_permissions_json': json.dumps(user_permissions_json),
            'ai_models': ai_models_list,
            'ai_models_json': json.dumps(ai_models_list),
        }
        
        return render(request, 'app_risk/risk_report.html', context)
        
    except Exception as e:
        logger.error(f"Error in risk_report view: {str(e)}")
        return render(request, 'app_risk/risk_report.html', {
            'error_message': 'An error occurred while loading the risk report page.'
        })


@login_required
@user_passes_test(has_risk_report_access)
@require_http_methods(["GET"])
def risk_report_guide(request):
    """Return JSON { content: html } for the Risk Report guide (localized)."""
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = RiskReportGuide.objects.first()
    if guide:
        if country:
            trans = RiskReportGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = RiskReportGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def risk_report_guide_translate(request):
    """API for AI translation of Risk Report guide content (admin)."""
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


# Report Profile API Views
@login_required
@user_passes_test(has_risk_report_access)
@require_GET
def get_report_profiles(request):
    """Get available report profiles for the current user"""
    try:
        # Check if user has access to risk reports
        if not has_risk_report_access(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to access risk reports')
            }, status=403)
        # Get available profiles for the user
        profiles = ReportProfile.get_available_profiles(request.user)
        
        # Filter by company if provided
        company_id = request.GET.get('company_id', '').strip()
        if company_id:
            logger.info(f"Filtering profiles by company_id: {company_id}")
            # Filter profiles by company stored in sections_config
            filtered_profiles = []
            for profile in profiles:
                profile_company_id = profile.sections_config.get('_company_id') if profile.sections_config else None
                logger.debug(f"Profile '{profile.name}': company_id={profile_company_id}, matches={profile_company_id == company_id}")
                if profile_company_id == company_id:
                    filtered_profiles.append(profile)
            logger.info(f"Filtered {len(profiles)} profiles to {len(filtered_profiles)} for company_id {company_id}")
            profiles = filtered_profiles
        
        # Pagination
        page = request.GET.get('page', 1)
        per_page = min(int(request.GET.get('per_page', 20)), 100)  # Max 100 per page
        
        paginator = Paginator(profiles, per_page)
        page_obj = paginator.get_page(page)
        
        # Serialize profiles
        profiles_data = []
        for profile in page_obj:
            company_id_from_config = profile.sections_config.get('_company_id') if profile.sections_config else None
            company_name = get_company_name_by_id(company_id_from_config)
            
            logger.info(f"Profile {profile.name}: sections_config={profile.sections_config}, company_id={company_id_from_config}, company_name={company_name}")
            
            profiles_data.append({
                'id': str(profile.id),
                'name': profile.name,
                'description': profile.description,
                'profile_type': profile.profile_type,
                'profile_type_display': profile.get_profile_type_display(),
                'created_by': profile.created_by.get_full_name() or profile.created_by.username,
                'created_by_id': profile.created_by.id,
                'company': company_name,
                'company_id': company_id_from_config,
                'sections_config': profile.get_sections_config(),
                'default_format': profile.default_format,
                'default_language': profile.default_language,
                'is_active': profile.is_active,
                'is_public': profile.is_public,
                'usage_count': profile.usage_count,
                'last_used_at': profile.last_used_at.isoformat() if profile.last_used_at else None,
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat(),
                'can_edit': profile.created_by == request.user or request.user.is_superuser,
                'can_delete': (profile.created_by == request.user and profile.profile_type != 'system') or (request.user.is_superuser and profile.profile_type != 'system'),
            })
        
        return JsonResponse({
            'status': 'success',
            'data': profiles_data,
            'pagination': {
                'page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index(),
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting report profiles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error loading report profiles: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(has_risk_report_access)
@require_GET
def get_report_profile_details(request, profile_id):
    """Get detailed information about a specific report profile"""
    try:
        # Check if user has access to risk reports
        if not has_risk_report_access(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to access risk reports')
            }, status=403)
        profile = ReportProfile.objects.get(id=profile_id)
        
        # Check if user can access this profile
        if not profile.can_be_used_by(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to access this profile'
            }, status=403)
        
        # Get allowed users info
        allowed_users_data = []
        for user in profile.allowed_users.all():
            allowed_users_data.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'email': user.email,
            })
        
        company_id_from_config = profile.sections_config.get('_company_id') if profile.sections_config else None
        company_name = get_company_name_by_id(company_id_from_config)
        
        logger.info(f"Profile details {profile.name}: sections_config={profile.sections_config}, company_id={company_id_from_config}, company_name={company_name}")
        
        profile_data = {
            'id': str(profile.id),
            'name': profile.name,
            'description': profile.description,
            'profile_type': profile.profile_type,
            'profile_type_display': profile.get_profile_type_display(),
            'created_by': {
                'id': profile.created_by.id,
                'username': profile.created_by.username,
                'full_name': profile.created_by.get_full_name() or profile.created_by.username,
                'email': profile.created_by.email,
            },
            'company': company_name,
            'company_id': company_id_from_config,
            'sections_config': profile.get_sections_config(),
            'default_format': profile.default_format,
            'default_language': profile.default_language,
            'is_active': profile.is_active,
            'is_public': profile.is_public,
            'allowed_users': allowed_users_data,
            'usage_count': profile.usage_count,
            'last_used_at': profile.last_used_at.isoformat() if profile.last_used_at else None,
            'created_at': profile.created_at.isoformat(),
            'updated_at': profile.updated_at.isoformat(),
            'can_edit': profile.created_by == request.user or request.user.is_superuser,
            'can_delete': (profile.created_by == request.user and profile.profile_type != 'system') or (request.user.is_superuser and profile.profile_type != 'system'),
        }
        
        return JsonResponse({
            'status': 'success',
            'data': profile_data
        })
        
    except ReportProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Report profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting report profile details: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error loading profile details: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(can_add_risk_report)
@require_POST
@csrf_exempt
def create_report_profile(request):
    """Create a new report profile"""
    try:
        # Check if user has permission to add reports
        if not can_add_risk_report(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to create report profiles')
            }, status=403)
        data = json.loads(request.body)
        
        # Validate required fields
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Profile name is required'
            }, status=400)
        
        # Check if profile name already exists for this user
        if ReportProfile.objects.filter(name=name, created_by=request.user).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'A profile with this name already exists'
            }, status=400)
        
        # Note: Company field is currently disabled in ReportProfile model
        company_id = data.get('company_id')
        logger.info(f"Processing company_id for new profile: {company_id} (type: {type(company_id)})")
        
        # Validate company_id is provided for new profiles
        if not company_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Company selection is required for new profiles'
            }, status=400)
        
        # Prepare sections config with company_id
        sections_config = data.get('sections_config', {})
        sections_config['_company_id'] = company_id  # Store company_id in sections_config
        
        # Create profile
        profile = ReportProfile.objects.create(
            name=name,
            description=data.get('description', ''),
            profile_type='user',  # Regular users can only create user profiles
            created_by=request.user,
            # company=company,  # Company field is currently disabled
            sections_config=sections_config,
            default_format=data.get('default_format', 'pdf'),
            default_language=data.get('default_language', 'uk'),
            is_active=True,
            is_public=data.get('is_public', False),
        )
        
        # Set allowed users if provided
        allowed_users_ids = data.get('allowed_users', [])
        if allowed_users_ids:
            from django.contrib.auth.models import User
            allowed_users = User.objects.filter(id__in=allowed_users_ids)
            profile.allowed_users.set(allowed_users)
        
        logger.info(f"User {request.user.username} created report profile: {profile.name}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Report profile created successfully',
            'data': {
                'id': str(profile.id),
                'name': profile.name,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating report profile: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating profile: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(can_edit_risk_report)
@require_POST
@csrf_exempt
def update_report_profile(request, profile_id):
    """Update an existing report profile"""
    try:
        # Check if user has permission to edit reports
        if not can_edit_risk_report(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to edit report profiles')
            }, status=403)
        profile = ReportProfile.objects.get(id=profile_id)
        
        # Check permissions
        if profile.created_by != request.user and not request.user.is_superuser:
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to edit this profile'
            }, status=403)
        
        # System profiles can only be edited by superusers
        if profile.profile_type == 'system' and not request.user.is_superuser:
            return JsonResponse({
                'status': 'error',
                'message': 'System profiles can only be edited by administrators'
            }, status=403)
        
        data = json.loads(request.body)
        
        logger.info(f"Updating profile {profile_id} with data: {data}")
        
        # Update fields
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Profile name is required'
                }, status=400)
            
            # Check if name already exists for this user (excluding current profile)
            if ReportProfile.objects.filter(name=name, created_by=request.user).exclude(id=profile.id).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'A profile with this name already exists'
                }, status=400)
            
            profile.name = name
        
        if 'description' in data:
            profile.description = data['description']
        
        # Handle sections_config and company_id together
        company_id = data.get('company_id')
        
        # Always update sections_config if provided in data
        if 'sections_config' in data:
            sections_config = data.get('sections_config', {})
            # Ensure it's a dict (not None)
            if not isinstance(sections_config, dict):
                sections_config = {}
            
            # Handle company_id - store it in sections_config since company field is disabled
            if company_id is not None:  # Allow empty string or None
                logger.info(f"Processing company_id: {company_id} (type: {type(company_id)})")
                sections_config['_company_id'] = company_id if company_id else None
            elif '_company_id' in (profile.sections_config or {}):
                # Preserve existing company_id if not being updated
                sections_config['_company_id'] = profile.sections_config.get('_company_id')
            
            profile.sections_config = sections_config
            logger.info(f"Updated sections_config with {len(sections_config)} sections")
        elif company_id is not None:
            # Only company_id is being updated, preserve existing sections_config
            sections_config = profile.sections_config or {}
            sections_config['_company_id'] = company_id if company_id else None
            profile.sections_config = sections_config
            logger.info(f"Updated company_id in sections_config")
        
        if 'default_format' in data:
            profile.default_format = data['default_format']
        
        if 'default_language' in data:
            profile.default_language = data['default_language']
        
        if 'is_active' in data:
            profile.is_active = data['is_active']
        
        if 'is_public' in data:
            profile.is_public = data['is_public']
        
        profile.save()
        
        # Update allowed users if provided
        if 'allowed_users' in data:
            from django.contrib.auth.models import User
            allowed_users_ids = data['allowed_users']
            allowed_users = User.objects.filter(id__in=allowed_users_ids)
            profile.allowed_users.set(allowed_users)
        
        logger.info(f"User {request.user.username} updated report profile: {profile.name}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Report profile updated successfully'
        })
        
    except ReportProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Report profile not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating report profile: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating profile: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(can_delete_risk_report)
@require_POST
@csrf_exempt
def delete_report_profile(request, profile_id):
    """Delete a report profile"""
    try:
        # Check if user has permission to delete reports
        if not can_delete_risk_report(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to delete report profiles')
            }, status=403)
        profile = ReportProfile.objects.get(id=profile_id)
        
        # Check permissions
        if profile.created_by != request.user and not request.user.is_superuser:
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to delete this profile'
            }, status=403)
        
        # System profiles cannot be deleted
        if profile.profile_type == 'system':
            return JsonResponse({
                'status': 'error',
                'message': 'System profiles cannot be deleted'
            }, status=403)
        
        profile_name = profile.name
        profile.delete()
        
        logger.info(f"User {request.user.username} deleted report profile: {profile_name}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Report profile "{profile_name}" deleted successfully'
        })
        
    except ReportProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Report profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting report profile: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting profile: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(can_add_risk_report)
@require_POST
@csrf_exempt
def duplicate_report_profile(request, profile_id):
    """Duplicate a report profile"""
    try:
        # Check if user has permission to add reports
        if not can_add_risk_report(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to create report profiles')
            }, status=403)
        original_profile = ReportProfile.objects.get(id=profile_id)
        
        # Check if user can access the original profile
        if not original_profile.can_be_used_by(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to access this profile'
            }, status=403)
        
        data = json.loads(request.body) if request.body else {}
        new_name = data.get('name', f"{original_profile.name} (Copy)")
        
        # Check if name already exists for this user
        counter = 1
        base_name = new_name
        while ReportProfile.objects.filter(name=new_name, created_by=request.user).exists():
            new_name = f"{base_name} ({counter})"
            counter += 1
        
        # Get user's company (temporarily disabled)
        # user_company = None
        # try:
        #     user_company = request.user.cabinetuser.company
        # except:
        #     pass
        
        # Create duplicate
        new_profile = ReportProfile.objects.create(
            name=new_name,
            description=data.get('description', original_profile.description),
            profile_type='user',  # Always create as user profile
            created_by=request.user,
            # company=user_company,  # Temporarily disabled
            sections_config=original_profile.sections_config.copy() if original_profile.sections_config else {},
            default_format=original_profile.default_format,
            default_language=original_profile.default_language,
            is_active=True,
            is_public=data.get('is_public', False),
        )
        
        logger.info(f"User {request.user.username} duplicated report profile: {original_profile.name} -> {new_profile.name}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Report profile duplicated as "{new_name}"',
            'data': {
                'id': str(new_profile.id),
                'name': new_profile.name,
            }
        })
        
    except ReportProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Report profile not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error duplicating report profile: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error duplicating profile: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(has_risk_report_access)
@require_POST
@csrf_exempt
def use_report_profile(request, profile_id):
    """Mark a report profile as used (increment usage count)"""
    try:
        # Check if user has access to risk reports
        if not has_risk_report_access(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('You do not have permission to access risk reports')
            }, status=403)
        profile = ReportProfile.objects.get(id=profile_id)
        
        # Check if user can use this profile
        if not profile.can_be_used_by(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to use this profile'
            }, status=403)
        
        # Increment usage
        profile.increment_usage()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Profile usage recorded',
            'data': {
                'sections_config': profile.get_sections_config(),
                'default_format': profile.default_format,
                'default_language': profile.default_language,
            }
        })
        
    except ReportProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Report profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error using report profile: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error using profile: {str(e)}'
        }, status=500)


