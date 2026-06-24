# SecBoard/app_std/ISO27002_view.py

import csv
import io
import json
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from .models import ISO27002Control, ISO27002Theme, AccessISO27002
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils.translation import get_language
from django.core.exceptions import PermissionDenied
from deep_translator import GoogleTranslator
import logging

logger = logging.getLogger(__name__)


def check_iso27002_access(user):
    """Check if user has basic access to ISO 27002 (any of user's groups grants access)."""
    if user.is_superuser:
        return True
    return AccessISO27002.objects.filter(
        group__in=user.groups.all(), has_access=True
    ).exists()


def check_iso27002_edit_access(user):
    """Check if user has edit access to ISO 27002 (any of user's groups grants edit)."""
    if user.is_superuser:
        return True
    return AccessISO27002.objects.filter(
        group__in=user.groups.all(), can_edit=True
    ).exists()


class ISO27002AccessMixin(UserPassesTestMixin):
    def test_func(self):
        return check_iso27002_access(self.request.user)


def translate_text(text, source_lang, target_lang):
    """Translate text using Google Translator"""
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    return translator.translate(text)


@login_required
def iso27002_controls(request):
    if not check_iso27002_access(request.user):
        raise PermissionDenied

    # Get user permissions
    can_edit = check_iso27002_edit_access(request.user)

    current_language = get_language()
    controls = ISO27002Control.objects.select_related('theme').all()

    fields = [
        'title', 'control_description', 'purpose', 'guidance', 'other_information'
    ]

    formatted_controls = []
    for control in controls:
        formatted_control = {
            'id': control.id,
            'control_number': control.control_number,
            'theme': control.theme.get_name_display(),
            'control_type': control.get_control_type_display(),
            'security_domain': control.get_security_domain_display(),
            'information_security_properties': control.information_security_properties,
            'cybersecurity_concepts': control.cybersecurity_concepts,
            'operational_capabilities': control.operational_capabilities,
        }

        for field in fields:
            getter = getattr(control, f'get_{field}', None)
            formatted_control[field] = getter(current_language) if callable(getter) else (getattr(control, field, '') or '')

        formatted_controls.append(formatted_control)

    context = {
        'controls': formatted_controls,
        'current_language': current_language,
        'languages': [('uk', 'Ukrainian'), ('ru', 'Russian'), ('en', 'English')],
        'fields': fields,
        'can_edit': can_edit,
        'controls_json': json.dumps(formatted_controls),
    }
    # print('context', context)
    return render(request, 'app_std/iso27002.html', context)


@require_POST
def edit_iso_control(request, control_id):
    if not check_iso27002_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        control = get_object_or_404(ISO27002Control, id=control_id)
        theme = control.theme

        # Update theme description (default + translations)
        if 'theme_description_en' in request.POST:
            theme.description = request.POST.get('theme_description_en', theme.description)
        for lang in ('uk', 'ru', 'en'):
            key = f'theme_description_{lang}'
            if key in request.POST:
                theme.set_description_for_language(lang, request.POST.get(key, ''))
        theme.save()

        # Update control fields (default + translations)
        fields = [
            'title', 'control_description', 'purpose', 'guidance', 'other_information'
        ]
        for field in fields:
            for lang in ['uk', 'ru', 'en']:
                field_name = f'{field}_{lang}'
                val = request.POST.get(field_name)
                if val is not None:
                    control.set_field_for_language(field, lang, val)
                    if lang == 'en' and hasattr(control, field):
                        setattr(control, field, val)

        # Update attribute fields
        control.control_type = request.POST.get('control_type', control.control_type)
        control.security_domain = request.POST.get('security_domain', control.security_domain)

        # Update JSON fields
        for json_field in ['information_security_properties', 'cybersecurity_concepts', 'operational_capabilities']:
            if json_field in request.POST:
                try:
                    value = json.loads(request.POST[json_field])
                    setattr(control, json_field, value)
                except json.JSONDecodeError:
                    pass

        control.save()

        return JsonResponse({
            'success': True,
            'message': 'Control updated successfully',
            'data': {
                'id': control.id,
                'control_number': control.control_number,
                'theme': control.theme.get_name_display(),
                'control_type': control.get_control_type_display(),
                'security_domain': control.get_security_domain_display(),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def get_iso_control(request, control_id):
    try:
        control = ISO27002Control.objects.select_related('theme').get(id=control_id)
        data = {
            'id': control.id,
            'control_number': control.control_number,
            'theme': {
                'name': control.theme.name,
                'description_uk': control.theme.get_description('uk'),
                'description_ru': control.theme.get_description('ru'),
                'description_en': control.theme.get_description('en'),
            },
            'title_uk': control.get_title('uk'),
            'title_ru': control.get_title('ru'),
            'title_en': control.get_title('en'),
            'control_description_uk': control.get_control_description('uk'),
            'control_description_ru': control.get_control_description('ru'),
            'control_description_en': control.get_control_description('en'),
            'purpose_uk': control.get_purpose('uk'),
            'purpose_ru': control.get_purpose('ru'),
            'purpose_en': control.get_purpose('en'),
            'guidance_uk': control.get_guidance('uk'),
            'guidance_ru': control.get_guidance('ru'),
            'guidance_en': control.get_guidance('en'),
            'other_information_uk': control.get_other_information('uk'),
            'other_information_ru': control.get_other_information('ru'),
            'other_information_en': control.get_other_information('en'),
            'control_type': control.control_type,
            'security_domain': control.security_domain,
            'information_security_properties': control.information_security_properties,
            'cybersecurity_concepts': control.cybersecurity_concepts,
            'operational_capabilities': control.operational_capabilities,
        }
        print('get_iso_control data = ',data )
        return JsonResponse(data)
    except ISO27002Control.DoesNotExist:
        return JsonResponse({'error': 'Control not found'}, status=404)


@require_POST
@login_required
def translate_iso27002_fields(request):
    """Handle ISO 27002 field translation requests"""
    if not check_iso27002_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
        if not data:
            return JsonResponse({'success': False, 'error': 'No data received'}, status=400)

        translations = {}
        fields = [
            'title', 'control_description', 'purpose', 'guidance', 'other_information'
        ]

        for control_id, fields_data in data.items():
            try:
                control = ISO27002Control.objects.select_related('theme').get(id=control_id)
            except ISO27002Control.DoesNotExist:
                continue

            translations[control_id] = {}

            for field in fields:
                source_lang = 'en'
                source_field = f"{field}_{source_lang}"

                if source_field in fields_data and fields_data[source_field]:
                    source_text = fields_data[source_field]

                    for target_lang in ['uk', 'ru']:
                        target_field = f"{field}_{target_lang}"
                        try:
                            translated_text = translate_text(source_text, source_lang, target_lang)
                            if translated_text:
                                translations[control_id][target_field] = translated_text
                                control.set_field_for_language(field, target_lang, translated_text)
                        except Exception as e:
                            logger.error(f"Translation error for {target_field}: {str(e)}")
                            continue

            try:
                control.save()
            except Exception as e:
                logger.error(f"Error saving control {control_id}: {str(e)}")
                continue

        return JsonResponse({'success': True, 'translations': translations})

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
def export_iso27002_controls(request):
    if not check_iso27002_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        controls = ISO27002Control.objects.filter(id__in=ids)

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="iso27002_controls.csv"'

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)

        headers = [
            'ID', 'Control Number', 'Theme',
            'Title (UK)', 'Title (RU)', 'Title (EN)',
            'Control Description (UK)', 'Control Description (RU)', 'Control Description (EN)',
            'Purpose (UK)', 'Purpose (RU)', 'Purpose (EN)',
            'Guidance (UK)', 'Guidance (RU)', 'Guidance (EN)',
            'Other Information (UK)', 'Other Information (RU)', 'Other Information (EN)',
            'Control Type', 'Security Domain',
            'Information Security Properties', 'Cybersecurity Concepts', 'Operational Capabilities'
        ]
        writer.writerow(headers)

        for control in controls:
            row = [
                control.id,
                control.control_number,
                control.theme.get_name_display(),
                control.get_title('uk'), control.get_title('ru'), control.get_title('en'),
                control.get_control_description('uk'), control.get_control_description('ru'), control.get_control_description('en'),
                control.get_purpose('uk'), control.get_purpose('ru'), control.get_purpose('en'),
                control.get_guidance('uk'), control.get_guidance('ru'), control.get_guidance('en'),
                control.get_other_information('uk'), control.get_other_information('ru'), control.get_other_information('en'),
                control.get_control_type_display(),
                control.get_security_domain_display(),
                json.dumps(control.information_security_properties),
                json.dumps(control.cybersecurity_concepts),
                json.dumps(control.operational_capabilities)
            ]

            row = ['' if v is None else str(v).strip() for v in row]
            writer.writerow(row)

        response.write(output.getvalue())
        return response

    except Exception as e:
        logger.error(f"Error in export_iso27002_controls: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
def import_iso27002_controls(request):
    if not check_iso27002_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        for row in data:
            theme, _ = ISO27002Theme.objects.get_or_create(
                name=row['Theme'],
                defaults={'description': ''}
            )

            control, created = ISO27002Control.objects.update_or_create(
                control_number=row['Control Number'],
                theme=theme,
                defaults={
                    'title': row.get('Title (EN)', '') or row.get('Title (UK)', ''),
                    'control_description': row.get('Control Description (EN)', '') or row.get('Control Description (UK)', ''),
                    'purpose': row.get('Purpose (EN)', '') or row.get('Purpose (UK)', ''),
                    'guidance': row.get('Guidance (EN)', '') or row.get('Guidance (UK)', ''),
                    'other_information': row.get('Other Information (EN)', '') or row.get('Other Information (UK)', ''),
                    'control_type': row['Control Type'],
                    'security_domain': row['Security Domain'],
                    'information_security_properties': json.loads(row['Information Security Properties']),
                    'cybersecurity_concepts': json.loads(row['Cybersecurity Concepts']),
                    'operational_capabilities': json.loads(row['Operational Capabilities'])
                }
            )
            for field, label in [
                ('title', 'Title'), ('control_description', 'Control Description'), ('purpose', 'Purpose'),
                ('guidance', 'Guidance'), ('other_information', 'Other Information')
            ]:
                control.set_field_for_language(field, 'uk', row.get(f'{label} (UK)', ''))
                control.set_field_for_language(field, 'ru', row.get(f'{label} (RU)', ''))
                control.set_field_for_language(field, 'en', row.get(f'{label} (EN)', ''))
            control.save()

        return JsonResponse({'success': True, 'message': 'Controls imported successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
@login_required
def add_iso_control(request):
    try:
        theme_name = request.POST.get('theme', '').upper()
        theme = ISO27002Theme.objects.filter(name=theme_name).first()

        if not theme:
            theme = ISO27002Theme.objects.create(name=theme_name, description='')

        def _parse_json(value, default=None):
            try:
                return json.loads(value) if value else (default or [])
            except (json.JSONDecodeError, TypeError):
                return default or []

        control = ISO27002Control.objects.create(
            control_number=request.POST.get('control_number'),
            theme=theme,
            control_type=request.POST.get('control_type'),
            security_domain=request.POST.get('security_domain', 'protection'),
            title=request.POST.get('title_en', '') or request.POST.get('title_uk', ''),
            control_description=request.POST.get('control_description_en', '') or request.POST.get('control_description_uk', ''),
            purpose=request.POST.get('purpose_en', '') or request.POST.get('purpose_uk', ''),
            guidance=request.POST.get('guidance_en', '') or request.POST.get('guidance_uk', ''),
            other_information=request.POST.get('other_information_en', '') or request.POST.get('other_information_uk', ''),
            information_security_properties=_parse_json(request.POST.get('information_security_properties'), []),
            cybersecurity_concepts=_parse_json(request.POST.get('cybersecurity_concepts'), []),
            operational_capabilities=_parse_json(request.POST.get('operational_capabilities'), []),
        )
        for field in ['title', 'control_description', 'purpose', 'guidance', 'other_information']:
            for lang in ['uk', 'ru', 'en']:
                val = request.POST.get(f'{field}_{lang}', '')
                if val is not None:
                    control.set_field_for_language(field, lang, val)
        control.save()
        return JsonResponse({'success': True, 'id': control.id})

    except Exception as e:
        logger.error(f"Error adding control: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
def delete_iso27002_controls(request):
    """Delete selected ISO 27002 controls"""
    if not check_iso27002_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        # Delete controls
        deleted_count = ISO27002Control.objects.filter(id__in=ids).delete()[0]

        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} controls deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error in delete_iso27002_controls: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)