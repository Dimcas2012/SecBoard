# SecBoard/app_risk/threat_views.py
import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
from .forms import ThreatForm
from .models import Threat, ThreatTranslation
from decimal import Decimal, ROUND_DOWN, InvalidOperation
import logging
from django.contrib.auth.decorators import user_passes_test
from .access_utils import has_risk_config_access, can_add_risk_config, can_edit_risk_config, can_delete_risk_config


logger = logging.getLogger(__name__)


logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")


@user_passes_test(can_edit_risk_config)
def edit_threat(request, threat_id):
    if request.method == 'GET':
        from .models import Threat as ThreatModel
        threat = get_object_or_404(Threat, id=threat_id)
        # Default: English (En) only — from main model fields
        data = {
            'id': threat.id,
            'name_en': (threat.name or '') or threat.get_translated_value('name', 'en'),
            'description_en': (threat.description or '') or threat.get_translated_value('description', 'en'),
            'risks_en': (threat.risks or '') or threat.get_translated_value('risks', 'en'),
            'probability_scenario': threat.probability_scenario,
            'probability': float(threat.probability),
            'impact': float(threat.impact),
            'scenario_m': threat.scenario_m,
            'scenario_n': threat.scenario_n,
            'financial_impact': threat.financial_impact.id if threat.financial_impact else None,
            'operational_impact': threat.operational_impact.id if threat.operational_impact else None,
            'reputational_impact': threat.reputational_impact.id if threat.reputational_impact else None,
        }
        return JsonResponse(data)
    elif request.method == 'POST':
        from .vulnerability_utils import get_vulnerability_form_languages
        post_data = request.POST.copy()
        # Map default English fields to form fields (Add/Edit modal sends only name_en, description_en, risks_en)
        post_data['name'] = (post_data.get('name_en') or post_data.get('name_uk') or post_data.get('name_ru') or '').strip()
        post_data['description'] = (post_data.get('description_en') or post_data.get('description_uk') or post_data.get('description_ru') or '').strip()
        post_data['risks'] = (post_data.get('risks_en') or post_data.get('risks_uk') or post_data.get('risks_ru') or '').strip()
        if threat_id:
            threat = get_object_or_404(Threat, id=threat_id)
            form = ThreatForm(post_data, instance=threat)
        else:
            form = ThreatForm(post_data)

        if form.is_valid():
            threat = form.save()
            # Save extra language fields (de, fr, etc.) from POST
            from .vulnerability_utils import get_vulnerability_form_languages
            from .models import Threat as ThreatModel
            for lang_code, _ in get_vulnerability_form_languages():
                if lang_code not in ('uk', 'ru', 'en'):
                    for field in ThreatModel.TRANSLATABLE_FIELDS:
                        key = f'{field}_{lang_code}'
                        if key in request.POST:
                            threat.set_translated_value(field, lang_code, request.POST.get(key, '') or '')
            threat.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Threat saved successfully',
                'id': threat.id,
                'probability': float(threat.probability)
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Error saving threat',
                'errors': form.errors
            }, status=400)
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=405)

@user_passes_test(can_delete_risk_config)
def delete_threat(request, threat_id):
    threat = get_object_or_404(Threat, id=threat_id)
    threat.delete()
    return JsonResponse({'status': 'success'})

@user_passes_test(has_risk_config_access)
def get_threats(request):
    from .vulnerability_utils import get_supported_risk_language
    raw_lang = request.GET.get('language', 'uk')
    # Activate language so Impact models use Country-based translations (e.g. Germany DE)
    from django.utils import translation
    translation.activate(raw_lang)
    threats = Threat.objects.prefetch_related('translations__country')
    data = []
    
    for threat in threats:
        try:
            # Calculate overall impact safely
            overall_impact = 0.0
            if hasattr(threat, 'calculate_overall_impact'):
                try:
                    result = threat.calculate_overall_impact()
                    if result is not None:
                        # Convert Decimal to float if needed
                        if hasattr(result, '__float__'):
                            overall_impact = float(result)
                        else:
                            overall_impact = float(result)
                    else:
                        overall_impact = 0.0
                except Exception as e:
                    print(f"Error calculating overall impact for threat {threat.id}: {str(e)}")
                    overall_impact = 0.0
            
            # Get impact names and colors (uses Country-based translations when lang activated)
            financial_impact = None
            if threat.financial_impact and hasattr(threat.financial_impact, 'get_name'):
                try:
                    financial_impact = {
                        'name': threat.financial_impact.get_name()[:10],
                        'color': threat.financial_impact.color
                    }
                except Exception as e:
                    financial_impact = None
            
            operational_impact = None
            if threat.operational_impact and hasattr(threat.operational_impact, 'get_name'):
                try:
                    operational_impact = {
                        'name': threat.operational_impact.get_name()[:10],
                        'color': threat.operational_impact.color
                    }
                except Exception as e:
                    operational_impact = None
            
            reputational_impact = None
            if threat.reputational_impact and hasattr(threat.reputational_impact, 'get_name'):
                try:
                    reputational_impact = {
                        'name': threat.reputational_impact.get_name()[:10],
                        'color': threat.reputational_impact.color
                    }
                except Exception as e:
                    reputational_impact = None
            
            threat_data = {
                'id': threat.id,
                'name': threat.get_name(raw_lang) or threat.get_name(),
                'description': threat.get_description(raw_lang) or threat.description,
                'risks': threat.get_risks(raw_lang) or threat.risks,
                'probability_scenario': threat.probability_scenario,
                'scenario_m': threat.scenario_m,
                'scenario_n': threat.scenario_n,
                'probability': float(threat.probability) if threat.probability is not None else 0.0,
                'impact': float(threat.impact) if threat.impact is not None else 0.0,
                'overall_impact': float(overall_impact) if overall_impact is not None else 0.0,
                'financial_impact': financial_impact,
                'operational_impact': operational_impact,
                'reputational_impact': reputational_impact,
                'translations': [
                    {'country_code': t.country.code, 'country_id': t.country_id, 'country_name': t.country.name}
                    for t in threat.translations.all()
                ],
            }
            data.append(threat_data)
        except Exception as e:
            # Log error and continue with other threats
            print(f"Error processing threat {threat.id}: {str(e)}")
            continue
    
    return JsonResponse({'threats': data})


@user_passes_test(has_risk_config_access)
@require_GET
def get_threat_translation_countries(request):
    """Return list of active countries that have a language mapping (same as vulnerability)."""
    try:
        from app_conf.models import Country
        from .models import LANGUAGE_COUNTRY_MAP
        country_codes = set()
        for codes in LANGUAGE_COUNTRY_MAP.values():
            country_codes.update((c or '').upper() for c in codes)
        all_countries = Country.objects.filter(is_active=True).order_by('name').values('id', 'name', 'code')
        countries = [c for c in all_countries if (c.get('code') or '').upper() in country_codes]
        return JsonResponse({'countries': countries})
    except Exception as e:
        logger.exception("get_threat_translation_countries")
        return JsonResponse({'error': str(e)}, status=500)


@user_passes_test(has_risk_config_access)
@require_GET
def get_threat_translation_detail(request):
    """Return one ThreatTranslation for threat_id and country_id (for viewing in modal)."""
    try:
        threat_id = request.GET.get('threat_id')
        country_id = request.GET.get('country_id')
        if not threat_id or not country_id:
            return JsonResponse({'error': _('threat_id and country_id required')}, status=400)
        trans = ThreatTranslation.objects.select_related('country').get(
            threat_id=threat_id,
            country_id=country_id
        )
        return JsonResponse({
            'country_code': trans.country.code,
            'country_name': trans.country.name,
            'name_local': trans.name_local or '',
            'description': trans.description or '',
            'risks': trans.risks or '',
        })
    except ThreatTranslation.DoesNotExist:
        return JsonResponse({'error': _('Translation not found')}, status=404)
    except Exception as e:
        logger.exception("get_threat_translation_detail")
        return JsonResponse({'error': str(e)}, status=500)


@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def save_threat_translation(request):
    """Create or update ThreatTranslation for one threat and country."""
    try:
        from app_conf.models import Country
        data = json.loads(request.body)
        threat_id = data.get('threat_id')
        country_id = data.get('country_id')
        if not threat_id or not country_id:
            return JsonResponse({'success': False, 'message': _('threat_id and country_id required')}, status=400)
        threat = Threat.objects.get(id=threat_id)
        country = Country.objects.get(id=country_id)
        trans, created = ThreatTranslation.objects.get_or_create(
            threat=threat,
            country=country,
            defaults={'name_local': '', 'description': '', 'risks': ''}
        )
        for key in ('name_local', 'description', 'risks'):
            if key in data:
                setattr(trans, key, data.get(key) or '')
        trans.save()
        return JsonResponse({'success': True, 'message': _('Translation saved')})
    except (Threat.DoesNotExist, Country.DoesNotExist) as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=404)
    except Exception as e:
        logger.exception("save_threat_translation")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@user_passes_test(has_risk_config_access)
def calculate_probability(request):
    scenario = request.GET.get('scenario')
    m = request.GET.get('m', '')
    n = request.GET.get('n', '')

    try:
        m = Decimal(m) if m else Decimal('0')
        n = Decimal(n) if n else Decimal('1')
    except InvalidOperation:
        return JsonResponse({'error': 'Invalid input for m or n'}, status=400)

    if scenario == 'daily':
        probability = Decimal('1')
    elif scenario == 'm_in_n_days':
        probability = min(Decimal('1'), m / n) if n != 0 else Decimal('0')
    elif scenario == 'once_in_n_years':
        probability = min(Decimal('1'), Decimal('1') / (n * Decimal('365'))) if n != 0 else Decimal('0')
    elif scenario == 'm_in_n_years':
        probability = min(Decimal('1'), m / (n * Decimal('365'))) if n != 0 else Decimal('0')
    else:
        probability = Decimal('0')

    # Округлення до 4 десяткових знаків
    probability = probability.quantize(Decimal('0.0001'), rounding=ROUND_DOWN)

    return JsonResponse({'probability': float(probability)})
