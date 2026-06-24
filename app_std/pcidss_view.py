# SecBoard/app_std/pcidss_view.py
import csv
import io
import json
import logging
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from .models import PCIDSSRequirement, PCIDSSCategory, AccessPCIDSS
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils.translation import get_language
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def translate_text(text, source_lang, target_lang):
    """
    Placeholder translation function.
    This should be replaced with actual translation service integration.
    """
    # TODO: Implement actual translation service
    return None



def check_pcidss_access(user):
    """Check if user has basic access to PCI DSS (any of user's groups grants access)."""
    if user.is_superuser:
        return True
    return AccessPCIDSS.objects.filter(
        group__in=user.groups.all(), has_access=True
    ).exists()


def check_pcidss_edit_access(user):
    """Check if user has edit access to PCI DSS (any of user's groups grants edit)."""
    if user.is_superuser:
        return True
    return AccessPCIDSS.objects.filter(
        group__in=user.groups.all(), can_edit=True
    ).exists()

class PCIDSSAccessMixin(UserPassesTestMixin):
    def test_func(self):
        return check_pcidss_access(self.request.user)


@login_required
def pcidss_requirements(request):
    if not check_pcidss_access(request.user):
        raise PermissionDenied

    # Get user permissions
    can_edit = check_pcidss_edit_access(request.user)

    current_language = get_language()
    requirements = PCIDSSRequirement.objects.select_related('category').filter(
        category__is_active=True
    ).all()

    fields = [
        'title', 'description', 'testing_procedures', 'further_information',
        'applicability_notes', 'customized_approach_objective', 'definitions',
        'examples', 'good_practice', 'purpose'
    ]

    formatted_requirements = []
    lang = (current_language or '')[:2].lower() or 'en'
    for req in requirements:
        formatted_req = {
            'id': req.id,
            'requirement_number': req.requirement_number,
            'category': req.category.get_name(lang) if req.category else '',
        }
        for field in fields:
            formatted_req[field] = getattr(req, f'get_{field}')(lang)
        formatted_requirements.append(formatted_req)

    context = {
        'requirements': formatted_requirements,
        'current_language': current_language,
        'languages': [('uk', 'Ukrainian'), ('ru', 'Russian'), ('en', 'English')],
        'fields': fields,
        'can_edit': can_edit,
    }
    return render(request, 'app_std/pcidss.html', context)


@require_POST
def edit_pcidss_requirement(request, requirement_id):
    if not check_pcidss_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    try:
        requirement = get_object_or_404(PCIDSSRequirement, id=requirement_id)
        category = requirement.category

        # Update category fields (name + translations)
        if 'name' in request.POST:
            category.name = request.POST.get('name', category.name)
        for lang in ('uk', 'ru', 'en'):
            key = f'category_{lang}'
            if key in request.POST:
                category.set_name_for_language(lang, request.POST.get(key, ''))
        category.save()

        # Update requirement fields
        fields = [
            'title', 'description', 'testing_procedures', 'further_information',
            'applicability_notes', 'customized_approach_objective', 'definitions',
            'examples', 'good_practice', 'purpose'
        ]

        for field in fields:
            for lang in ['uk', 'ru', 'en']:
                field_name = f'{field}_{lang}'
                val = request.POST.get(field_name)
                if val is not None:
                    requirement.set_field_for_language(field, lang, val)
                    if lang == 'en' and hasattr(requirement, field):
                        setattr(requirement, field, val)
        requirement.save()

        # Prepare response data
        response_data = {
            'success': True,
            'message': 'Requirement updated successfully',
            'data': {
                'id': requirement.id,
                'requirement_number': requirement.requirement_number,
                'category': {
                    'category_uk': category.get_name('uk'),
                    'category_ru': category.get_name('ru'),
                    'category_en': category.get_name('en'),
                },
            }
        }

        # Add other fields to response data
        for field in fields:
            for lang in ['uk', 'ru', 'en']:
                field_name = f'{field}_{lang}'
                response_data['data'][field_name] = getattr(requirement, f'get_{field}')(lang)

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def get_pcidss_requirement(request, requirement_id):
    try:
        requirement = PCIDSSRequirement.objects.select_related('category').get(id=requirement_id)
        data = {
            'id': requirement.id,
            'requirement_number': requirement.requirement_number,
            'category': {
                'category_uk': requirement.category.get_name('uk') if requirement.category else '',
                'category_ru': requirement.category.get_name('ru') if requirement.category else '',
                'category_en': requirement.category.get_name('en') if requirement.category else '',
            },
            'title_uk': requirement.get_title('uk'),
            'title_ru': requirement.get_title('ru'),
            'title_en': requirement.get_title('en'),
            'description_uk': requirement.get_description('uk'),
            'description_ru': requirement.get_description('ru'),
            'description_en': requirement.get_description('en'),
            'testing_procedures_uk': requirement.get_testing_procedures('uk'),
            'testing_procedures_ru': requirement.get_testing_procedures('ru'),
            'testing_procedures_en': requirement.get_testing_procedures('en'),
            'further_information_uk': requirement.get_further_information('uk'),
            'further_information_ru': requirement.get_further_information('ru'),
            'further_information_en': requirement.get_further_information('en'),
            'applicability_notes_uk': requirement.get_applicability_notes('uk'),
            'applicability_notes_ru': requirement.get_applicability_notes('ru'),
            'applicability_notes_en': requirement.get_applicability_notes('en'),
            'customized_approach_objective_uk': requirement.get_customized_approach_objective('uk'),
            'customized_approach_objective_ru': requirement.get_customized_approach_objective('ru'),
            'customized_approach_objective_en': requirement.get_customized_approach_objective('en'),
            'definitions_uk': requirement.get_definitions('uk'),
            'definitions_ru': requirement.get_definitions('ru'),
            'definitions_en': requirement.get_definitions('en'),
            'examples_uk': requirement.get_examples('uk'),
            'examples_ru': requirement.get_examples('ru'),
            'examples_en': requirement.get_examples('en'),
            'good_practice_uk': requirement.get_good_practice('uk'),
            'good_practice_ru': requirement.get_good_practice('ru'),
            'good_practice_en': requirement.get_good_practice('en'),
            'purpose_uk': requirement.get_purpose('uk'),
            'purpose_ru': requirement.get_purpose('ru'),
            'purpose_en': requirement.get_purpose('en'),
        }
        # print(f"Returning data for requirement {requirement_id}:", data)
        return JsonResponse(data)
    except PCIDSSRequirement.DoesNotExist:
        return JsonResponse({'error': 'Requirement not found'}, status=404)

@require_POST
@login_required
def translate_pcidss_fields(request):
    """Handle PCI DSS field translation requests"""
    if not check_pcidss_edit_access(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    try:
        # Decode request body as UTF-8
        body_unicode = request.body.decode('utf-8')
        try:
            data = json.loads(body_unicode)
        except json.JSONDecodeError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid JSON data: {str(e)}'
            }, status=400)

        if not data:
            return JsonResponse({
                'success': False,
                'error': 'No data received for translation'
            }, status=400)

        translations = {}
        fields = [
            'category', 'title', 'description', 'testing_procedures',
            'further_information', 'applicability_notes',
            'customized_approach_objective', 'definitions',
            'examples', 'good_practice', 'purpose'
        ]

        for requirement_id, fields_data in data.items():
            try:
                requirement = PCIDSSRequirement.objects.select_related('category').get(id=requirement_id)
            except PCIDSSRequirement.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Requirement {requirement_id} not found'
                }, status=404)

            translations[requirement_id] = {}

            for field in fields:
                source_lang = 'en'  # We're translating from English
                source_field = f"{field}_{source_lang}"

                if source_field in fields_data and fields_data[source_field]:
                    source_text = fields_data[source_field]

                    for target_lang in ['uk', 'ru']:  # Translate to Ukrainian and Russian
                        target_field = f"{field}_{target_lang}"

                        try:
                            translated_text = translate_text(
                                source_text,
                                source_lang,
                                target_lang
                            )

                            if translated_text:
                                translations[requirement_id][target_field] = translated_text
                                if field == 'category':
                                    requirement.category.set_name_for_language(target_lang, translated_text)
                                else:
                                    requirement.set_field_for_language(field, target_lang, translated_text)

                        except Exception as e:
                            print(f"Translation error for {target_field}: {str(e)}")
                            continue

            try:
                if hasattr(requirement, 'category') and requirement.category:
                    requirement.category.save()
                requirement.save()
            except Exception as e:
                print(f"Error saving requirement {requirement_id}: {str(e)}")
                continue

        return JsonResponse({
            'success': True,
            'translations': translations
        })

    except Exception as e:
        print(f"Translation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
@login_required
def export_pcidss_requirements(request):
    if not check_pcidss_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        requirements = PCIDSSRequirement.objects.filter(id__in=ids)

        # Створюємо response з BOM для UTF-8
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="pci_dss_requirements.csv"'

        # Використовуємо StringIO для буферизації
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)

        # Записуємо заголовки
        headers = [
            'ID', 'Requirement Number',
            'Category (UK)', 'Category (RU)', 'Category (EN)',
            'Title (UK)', 'Title (RU)', 'Title (EN)',
            'Description (UK)', 'Description (RU)', 'Description (EN)',
            'Testing Procedures (UK)', 'Testing Procedures (RU)', 'Testing Procedures (EN)',
            'Further Information (UK)', 'Further Information (RU)', 'Further Information (EN)',
            'Applicability Notes (UK)', 'Applicability Notes (RU)', 'Applicability Notes (EN)',
            'Customized Approach Objective (UK)', 'Customized Approach Objective (RU)',
            'Customized Approach Objective (EN)',
            'Definitions (UK)', 'Definitions (RU)', 'Definitions (EN)',
            'Examples (UK)', 'Examples (RU)', 'Examples (EN)',
            'Good Practice (UK)', 'Good Practice (RU)', 'Good Practice (EN)',
            'Purpose (UK)', 'Purpose (RU)', 'Purpose (EN)'
        ]
        writer.writerow(headers)

        # Записуємо дані
        for req in requirements:
            cat = req.category
            row = [
                req.id,
                req.requirement_number,
                cat.get_name('uk') if cat else '',
                cat.get_name('ru') if cat else '',
                cat.get_name('en') if cat else '',
                req.get_title('uk'), req.get_title('ru'), req.get_title('en'),
                req.get_description('uk'), req.get_description('ru'), req.get_description('en'),
                req.get_testing_procedures('uk'), req.get_testing_procedures('ru'), req.get_testing_procedures('en'),
                req.get_further_information('uk'), req.get_further_information('ru'), req.get_further_information('en'),
                req.get_applicability_notes('uk'), req.get_applicability_notes('ru'), req.get_applicability_notes('en'),
                req.get_customized_approach_objective('uk'), req.get_customized_approach_objective('ru'),
                req.get_customized_approach_objective('en'),
                req.get_definitions('uk'), req.get_definitions('ru'), req.get_definitions('en'),
                req.get_examples('uk'), req.get_examples('ru'), req.get_examples('en'),
                req.get_good_practice('uk'), req.get_good_practice('ru'), req.get_good_practice('en'),
                req.get_purpose('uk'), req.get_purpose('ru'), req.get_purpose('en'),
            ]

            # Обробляємо None значення та прибираємо зайві пробіли
            row = ['' if v is None else str(v).strip() for v in row]

            try:
                writer.writerow(row)
            except UnicodeEncodeError as e:
                logger.error(f"UnicodeEncodeError while writing row: {e}")
                logger.error(f"Problematic row: {row}")
                continue

        # Записуємо результат у response
        response.write(output.getvalue())
        return response

    except Exception as e:
        logger.error(f"Error in export_pcidss_requirements: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_POST
@login_required
def import_pcidss_requirements(request):
    if not check_pcidss_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    try:
        data = json.loads(request.body)
        for row in data:
            name = (row.get('Category (EN)') or row.get('Category (UK)') or '')[:255]
            category, created = PCIDSSCategory.objects.get_or_create(
                category_id=row['Requirement Number'],
                defaults={'name': name or ''}
            )
            if name or row.get('Category (UK)') or row.get('Category (RU)'):
                category.set_name_for_language('en', row.get('Category (EN)', ''))
                category.set_name_for_language('uk', row.get('Category (UK)', ''))
                category.set_name_for_language('ru', row.get('Category (RU)', ''))
                if not category.name:
                    category.name = name or category.get_name_by_language('en') or category.get_name_by_language('uk')
                category.save()

            req_defaults = {
                'title': row.get('Title (EN)', '') or row.get('Title (UK)', ''),
                'description': row.get('Description (EN)', '') or row.get('Description (UK)', ''),
                'testing_procedures': row.get('Testing Procedures (EN)', '') or row.get('Testing Procedures (UK)', ''),
                'further_information': row.get('Further Information (EN)', '') or row.get('Further Information (UK)', ''),
                'applicability_notes': row.get('Applicability Notes (EN)', '') or row.get('Applicability Notes (UK)', ''),
                'customized_approach_objective': row.get('Customized Approach Objective (EN)', '') or row.get('Customized Approach Objective (UK)', ''),
                'definitions': row.get('Definitions (EN)', '') or row.get('Definitions (UK)', ''),
                'examples': row.get('Examples (EN)', '') or row.get('Examples (UK)', ''),
                'good_practice': row.get('Good Practice (EN)', '') or row.get('Good Practice (UK)', ''),
                'purpose': row.get('Purpose (EN)', '') or row.get('Purpose (UK)', ''),
            }
            requirement, created = PCIDSSRequirement.objects.update_or_create(
                requirement_number=row['Requirement Number'],
                category=category,
                defaults=req_defaults
            )
            _csv_cols = [
                ('title', 'Title'), ('description', 'Description'), ('testing_procedures', 'Testing Procedures'),
                ('further_information', 'Further Information'), ('applicability_notes', 'Applicability Notes'),
                ('customized_approach_objective', 'Customized Approach Objective'), ('definitions', 'Definitions'),
                ('examples', 'Examples'), ('good_practice', 'Good Practice'), ('purpose', 'Purpose'),
            ]
            for field, label in _csv_cols:
                requirement.set_field_for_language(field, 'uk', row.get(f'{label} (UK)', ''))
                requirement.set_field_for_language(field, 'ru', row.get(f'{label} (RU)', ''))
                requirement.set_field_for_language(field, 'en', row.get(f'{label} (EN)', ''))
            requirement.save()
        return JsonResponse({'success': True, 'message': 'Requirements imported successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@require_POST
@login_required
def add_pcidss_requirement(request):
    if not check_pcidss_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        # Create or get category
        category_uk = request.POST.get('category_uk', '')
        category_ru = request.POST.get('category_ru', '')
        category_en = request.POST.get('category_en', '')
        name = request.POST.get('name', '') or category_en or category_uk
        category = PCIDSSCategory.objects.create(
            category_id=request.POST.get('requirement_number'),
            name=name or ''
        )
        category.set_name_for_language('uk', category_uk)
        category.set_name_for_language('ru', category_ru)
        category.set_name_for_language('en', category_en)
        if not category.name:
            category.name = name or category.get_name_by_language('en') or category.get_name_by_language('uk')
        category.save()

        # Create requirement
        fields = [
            'title', 'description', 'testing_procedures', 'further_information',
            'applicability_notes', 'customized_approach_objective', 'definitions',
            'examples', 'good_practice', 'purpose'
        ]

        requirement = PCIDSSRequirement.objects.create(
            requirement_number=request.POST.get('requirement_number'),
            category=category,
            title=request.POST.get('title_en', '') or request.POST.get('title_uk', ''),
            description=request.POST.get('description_en', '') or request.POST.get('description_uk', ''),
            testing_procedures=request.POST.get('testing_procedures_en', '') or request.POST.get('testing_procedures_uk', ''),
            further_information=request.POST.get('further_information_en', '') or request.POST.get('further_information_uk', ''),
            applicability_notes=request.POST.get('applicability_notes_en', '') or request.POST.get('applicability_notes_uk', ''),
            customized_approach_objective=request.POST.get('customized_approach_objective_en', '') or request.POST.get('customized_approach_objective_uk', ''),
            definitions=request.POST.get('definitions_en', '') or request.POST.get('definitions_uk', ''),
            examples=request.POST.get('examples_en', '') or request.POST.get('examples_uk', ''),
            good_practice=request.POST.get('good_practice_en', '') or request.POST.get('good_practice_uk', ''),
            purpose=request.POST.get('purpose_en', '') or request.POST.get('purpose_uk', ''),
        )
        for field in fields:
            for lang in ['uk', 'ru', 'en']:
                val = request.POST.get(f'{field}_{lang}', '')
                if val is not None:
                    requirement.set_field_for_language(field, lang, val)
        requirement.save()

        return JsonResponse({
            'success': True,
            'message': 'Requirement created successfully',
            'data': {'id': requirement.id}
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
@login_required
def delete_pcidss_requirements(request):
    if not check_pcidss_edit_access(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        PCIDSSRequirement.objects.filter(id__in=ids).delete()

        return JsonResponse({
            'success': True,
            'message': 'Requirements deleted successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)