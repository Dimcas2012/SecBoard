# SecBoard/app_risk/ai_views.py
import json
import re
import anthropic
from anthropic import Anthropic
try:
    from anthropic import NotFoundError as AnthropicNotFoundError
except ImportError:
    AnthropicNotFoundError = None  # older SDK may not define it
from deep_translator import GoogleTranslator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from app_ai.models import APISettingsClaude
from app_std.models import PCIDSSRequirement,PCIDSSCategory, ISO27002Control, ISO27002Theme
from app_asset.models import AssetGroup, AssetType
import logging
from django.utils.translation import get_language
from .models import Vulnerability, Threat
from django.contrib.auth.decorators import user_passes_test
from .access_utils import can_edit_risk_config, can_add_risk_config


logger = logging.getLogger(__name__)


def _get_source_value(data, prefix):
    """Get first non-empty value for prefix_{lang} from data (dynamic langs)."""
    from .vulnerability_utils import get_vulnerability_form_languages
    for code, _ in get_vulnerability_form_languages():
        val = data.get(f'{prefix}_{code}', '') or ''
        if val and str(val).strip():
            return val
    return ''


def _translate_to_form_languages(text, source_lang='en'):
    """
    Translate text to all form languages except source. Returns {lang: translated_text}.
    Used by AI endpoints to support dynamic additional languages (DE, FR, etc.).
    """
    from .vulnerability_utils import get_vulnerability_form_languages
    result = {}
    if not text or not str(text).strip():
        return result
    for code, _ in get_vulnerability_form_languages():
        if code == source_lang:
            result[code] = text
            continue
        try:
            translator = GoogleTranslator(source=source_lang, target=code)
            result[code] = translator.translate(str(text))
        except Exception as e:
            logger.warning(f"Translation to {code} failed: {e}, using source")
            result[code] = str(text)
    return result


def _translate_text_to_lang(text, source_lang='en', target_lang='uk'):
    """Translate a single text to one target language. Returns translated string or original if empty/fail."""
    if not text or not str(text).strip():
        return ''
    try:
        return GoogleTranslator(source=source_lang, target=target_lang).translate(str(text))
    except Exception as e:
        logger.warning(f"Translation to {target_lang} failed: {e}, using source")
        return str(text)




@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def analyze_threats_ai(request):
    try:
        data = json.loads(request.body)
        
        # Get the AI provider from query parameters, default to Claude (ignore invalid e.g. [object HTMLSelectElement])
        _provider = (request.GET.get('provider') or 'claude').lower()
        ai_provider = _provider if _provider in ('google', 'groq', 'deepseek', 'claude') else 'claude'
        logger.info(f"Using AI provider for threat analysis: {ai_provider}")

        # Build prompt from all configured languages (dynamic: uk, ru, en, de, etc.)
        from .vulnerability_utils import get_vulnerability_form_languages
        def _field_str(prefix):
            parts = []
            for code, name in get_vulnerability_form_languages():
                val = data.get(f'{prefix}_{code}', '') or ''
                if val:
                    parts.append(f"{name}: {val[:200]}{'...' if len(val) > 200 else ''}")
            return ' / '.join(parts) if parts else '-'

        prompt = f"""Analyze the following vulnerability information and determine which threats from the existing list are most relevant. The vulnerability details are:

Asset Group: {data.get('asset_group', '')}
Asset Type: {data.get('asset_type', '')}
Scope: {_field_str('scope')}
Vulnerability: {_field_str('vulnerability')}
Risk Mitigation Controls: {_field_str('risk_mitigation_controls')}
PCI DSS Requirement: {_field_str('pci_dss_requirement')}
ISO27001 Requirement: {_field_str('iso27001_requirement')}
Note: {_field_str('note')}

Based on this information, which of the following threats are most relevant? Reply with ONLY a comma- or space-separated list of threat IDs (numbers), nothing else. Example: 1, 5, 12

Existing Threats:
"""

        # Get all existing threats
        threats = Threat.objects.all()
        for threat in threats:
            prompt += f"{threat.id}: {threat.get_name_by_language('uk')} / {threat.get_name_by_language('ru')} / {threat.get_name_by_language('en')}\n"

        ai_response = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'success': False, 'error': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                ai_response = response.text
                
                logger.info(f"Google AI threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("Google AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'error': 'Google AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'error': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'success': False, 'error': 'Groq API settings not configured'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"Groq AI threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("Groq AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'error': 'Groq AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'error': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings or not getattr(deepseek_settings, 'model_name', None):
                return JsonResponse({'success': False, 'error': 'DeepSeek API settings not configured'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant. Reply with only a comma- or space-separated list of threat IDs (numbers). No explanation."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=getattr(deepseek_settings, 'temperature', 0.3) or 0.3,
                    max_tokens=getattr(deepseek_settings, 'max_tokens', 2048) or 2048,
                    top_p=getattr(deepseek_settings, 'top_p', 1.0),
                    frequency_penalty=getattr(deepseek_settings, 'frequency_penalty', 0) or 0,
                    presence_penalty=getattr(deepseek_settings, 'presence_penalty', 0) or 0,
                )
                raw = response.choices[0].message.content if response.choices else None
                if isinstance(raw, list):
                    ai_response = ''.join(
                        (b.get('text', '') if isinstance(b, dict) else getattr(b, 'text', '') for b in raw))
                else:
                    ai_response = (raw or '').strip()
                
                logger.info(f"DeepSeek AI threat analysis response received, length: {len(ai_response)}")
                
                if not ai_response or len(ai_response) < 1:
                    logger.warning("DeepSeek AI returned an empty response")
                    return JsonResponse({
                        'success': True,
                        'threats': [],
                        'message': 'DeepSeek returned no threat IDs. Try adding more vulnerability details or use another provider.'
                    })
                if len(ai_response.strip()) < 2:
                    return JsonResponse({
                        'success': False,
                        'error': 'DeepSeek AI returned an invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'error': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'error': 'Claude API settings not configured'}, status=500)
            if not getattr(claude_settings, 'model_name', None):
                return JsonResponse({'success': False, 'error': 'Claude model not selected in API settings'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                ai_response = response.content[0].text
                logger.info(f"Claude AI threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("Claude AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'error': 'Claude AI returned an empty or invalid response. Please try again.'
                    }, status=400)
            except Exception as e:
                logger.error(f"Error using Claude AI for threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'error': f'Error using Claude AI: {str(e)}'}, status=500)

        # Safely get string content (some providers return None or list)
        if ai_response is None:
            ai_response = ''
        if isinstance(ai_response, list):
            ai_response = ''.join(
                (x.get('text', '') if isinstance(x, dict) else getattr(x, 'text', '')) for x in ai_response
            )
        ai_response = (ai_response or '').strip()

        # Use regex to find all numbers in the response, then keep only IDs that exist
        try:
            raw_ids = [int(x) for x in re.findall(r'\d+', ai_response)]
        except (ValueError, TypeError):
            raw_ids = []
        valid_ids = list(Threat.objects.filter(id__in=raw_ids).values_list('id', flat=True))

        if not valid_ids:
            logger.warning("No valid threat IDs found in AI response: %s", ai_response[:200] if ai_response else "(empty)")
            return JsonResponse({
                'success': True,
                'threats': [],
                'message': f'No threat IDs could be identified in the {ai_provider.capitalize()} AI response. Try adding more vulnerability details.'
            })

        return JsonResponse({'success': True, 'threats': valid_ids})

    except Exception as e:
        logger.error(f"Error in analyze_threats_ai: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@user_passes_test(can_add_risk_config)
@csrf_exempt
@require_POST
def generate_vulnerabilities_ai(request):
    try:
        print("Starting generate_vulnerabilities_ai function")
        logger.info("Starting generate_vulnerabilities_ai function")

        data = json.loads(request.body)
        print(f"Received data: {data}")
        logger.debug(f"Received data: {data}")

        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider: {ai_provider}")

        asset_group = AssetGroup.objects.get(id=data['asset_group'])
        asset_type = AssetType.objects.get(id=data['asset_type'])
        
        # Get the user hint if provided
        user_hint = data.get('hint', '').strip()
        logger.info(f"User provided hint: {user_hint[:100]}..." if len(user_hint) > 100 else f"User provided hint: {user_hint}")

        # Get existing vulnerabilities for this asset type (model uses name, scope)
        existing_vulnerabilities = Vulnerability.objects.filter(
            asset_type=asset_type
        ).values_list('name', 'scope')

        existing_vulns_set = {(v[0], v[1]) for v in existing_vulnerabilities}
        existing_vulns_text = "\n".join([
            f"Existing vulnerability: {v[0]}\nScope: {v[1]}"
            for v in existing_vulnerabilities
        ])

        prompt = f"""Based on the following asset information, generate new unique vulnerabilities that are NOT already in the existing list:

        Asset Group: {asset_group.name}
        Asset Type: {asset_type.name}

        Existing Vulnerabilities:
        {existing_vulns_text}
        """
        
        # Add user hint to the prompt if provided
        if user_hint:
            prompt += f"\nAdditional guidance for vulnerability generation:\n{user_hint}\n"
            
        prompt += """
        Please generate 5 NEW and UNIQUE vulnerabilities. For each vulnerability, provide ONLY:

        Vulnerability: [Name of the vulnerability]
        Scope: [Scope description]

        Requirements:
        1. Each vulnerability must be completely different from the existing ones
        2. Format each vulnerability exactly as shown above
        3. Do not include any additional information or commentary
        4. Separate each vulnerability with a blank line
        """

        ai_response = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'error': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                ai_response = response.text
                
                logger.info(f"Google AI response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 20:
                    logger.error("Google AI returned an empty or too short response")
                    return JsonResponse({
                        'error': 'Google AI returned an empty or invalid response. Please try again.',
                        'vulnerabilities': []
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI: {str(e)}", exc_info=True)
                return JsonResponse({'error': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'error': 'Groq API settings not configured'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"Groq AI response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 20:
                    logger.error("Groq AI returned an empty or too short response")
                    return JsonResponse({
                        'error': 'Groq AI returned an empty or invalid response. Please try again.',
                        'vulnerabilities': []
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI: {str(e)}", exc_info=True)
                return JsonResponse({'error': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'error': 'DeepSeek API settings not configured'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates unique vulnerabilities based on asset information."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 20:
                    logger.error("DeepSeek AI returned an empty or too short response")
                    return JsonResponse({
                        'error': 'DeepSeek AI returned an empty or invalid response. Please try again.',
                        'vulnerabilities': []
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI: {str(e)}", exc_info=True)
                return JsonResponse({'error': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'error': 'Claude API settings not configured'}, status=500)

            client = Anthropic(api_key=claude_settings.api_key)
            response = client.messages.create(
                model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                max_tokens=claude_settings.max_tokens,
                temperature=claude_settings.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            ai_response = response.content[0].text
            logger.info(f"Claude AI response received, length: {len(ai_response)}")
            
            # Check if response is empty or too short
            if not ai_response or len(ai_response.strip()) < 20:
                logger.error("Claude AI returned an empty or too short response")
                return JsonResponse({
                    'error': 'Claude AI returned an empty or invalid response. Please try again.',
                    'vulnerabilities': []
                }, status=400)

        print(f"AI response content: {ai_response}")

        # Parse vulnerabilities
        vulnerabilities = parse_ai_vulnerabilities(ai_response)
        if not vulnerabilities:
            logger.warning(f"Failed to parse any vulnerabilities from AI response: {ai_response[:200]}...")
            return JsonResponse({
                'vulnerabilities': [],
                'error': f'No valid vulnerabilities could be parsed from the {ai_provider.capitalize()} AI response. Please try again.'
            }, status=400)

        # Filter out any duplicates with existing vulnerabilities
        from .vulnerability_utils import get_vulnerability_form_languages
        lang_config = get_vulnerability_form_languages()
        lang_codes = [code for code, _ in lang_config]
        # AI generates in English; use as base for other languages
        source_lang = 'en' if 'en' in lang_codes else (lang_codes[0] if lang_codes else 'en')

        new_vulnerabilities = []
        for vuln in vulnerabilities:
            if vuln.get('vulnerability') and vuln.get('scope'):  # Verify both fields exist
                vuln_tuple = (vuln['vulnerability'], vuln['scope'])
                if vuln_tuple not in existing_vulns_set:
                    # Translate to all configured form languages (uk, ru, de, etc.)
                    trans_vuln = _translate_to_form_languages(vuln['vulnerability'], source_lang)
                    trans_scope = _translate_to_form_languages(vuln['scope'], source_lang)
                    for lang_code, val in trans_vuln.items():
                        vuln['vulnerability_' + lang_code] = val
                    for lang_code, val in trans_scope.items():
                        vuln['scope_' + lang_code] = val
                    new_vulnerabilities.append(vuln)

        if not new_vulnerabilities:
            return JsonResponse({
                'vulnerabilities': [],
                'message': f'All generated vulnerabilities already exist in the database. Please try again with different parameters.'
            })

        return JsonResponse({
            'vulnerabilities': new_vulnerabilities,
            'message': f'Generated {len(new_vulnerabilities)} new vulnerabilities using {ai_provider.capitalize()} AI.'
        })

    except Exception as e:
        print(f"Error in generate_vulnerabilities_ai: {str(e)}")
        logger.error(f"Error in generate_vulnerabilities_ai: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


def parse_ai_vulnerabilities(response):
    try:
        vulnerabilities = []
        current_vuln = {}

        lines = response.split('\n')
        for line in lines:
            line = line.strip()

            # Skip empty lines and store complete vulnerability
            if not line:
                if current_vuln.get('vulnerability') and current_vuln.get('scope'):
                    vulnerabilities.append(current_vuln.copy())
                current_vuln = {}
                continue

            # Parse line if it contains a colon
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()

                if key == 'vulnerability':
                    current_vuln['vulnerability'] = value
                elif key == 'scope':
                    current_vuln['scope'] = value

        # Don't forget the last vulnerability if it exists
        if current_vuln.get('vulnerability') and current_vuln.get('scope'):
            vulnerabilities.append(current_vuln.copy())

        print(f"Parsed vulnerabilities: {vulnerabilities}")
        
        # Log warning if no vulnerabilities were parsed
        if not vulnerabilities:
            logger.warning(f"No vulnerabilities parsed from response: {response[:200]}...")
            
        return vulnerabilities if vulnerabilities else []

    except Exception as e:
        print(f"Error parsing vulnerabilities: {str(e)}")
        logger.error(f"Error parsing vulnerabilities: {str(e)}", exc_info=True)
        return []



@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def generate_note_ai(request):
    try:
        data = json.loads(request.body)
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for note generation: {ai_provider}")

        scope_val = _get_source_value(data, 'scope') or data.get('scope_en', '')
        vuln_val = _get_source_value(data, 'vulnerability') or data.get('vulnerability_en', '')
        desc_val = _get_source_value(data, 'description') or data.get('description_en', '')
        risk_val = _get_source_value(data, 'risk_mitigation_controls') or data.get('risk_mitigation_controls_en', '')
        pci_val = _get_source_value(data, 'pci_dss_requirement') or data.get('pci_dss_requirement_en', '')
        iso_val = _get_source_value(data, 'iso27001_requirement') or data.get('iso27001_requirement_en', '')
        threats_raw = data.get('threats', [])
        threats_str = ', '.join(str(t) for t in (threats_raw if isinstance(threats_raw, (list, tuple)) else []))
        prompt = f"""Based on the following vulnerability information, provide a concise note with additional recommendations or considerations:

        Scope: {scope_val}
        Vulnerability: {vuln_val}
        Description: {desc_val}
        Threats: {threats_str}
        Risk Mitigation Controls: {risk_val}
        PCI DSS Requirement: {pci_val}
        ISO27001 Requirement: {iso_val}

        Please provide a brief note with additional recommendations or considerations that are not already covered in the existing information. Do not include any introductory phrases like "Here's a brief note" or similar.
        """
        
        note_en = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'success': False, 'message': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                note_en = ''
                try:
                    note_en = getattr(response, 'text', None) or ''
                except (ValueError, AttributeError, Exception):
                    pass
                if not (note_en and note_en.strip()) and getattr(response, 'candidates', None):
                    try:
                        c = response.candidates[0]
                        if getattr(c, 'content', None) and getattr(c.content, 'parts', None) and c.content.parts:
                            note_en = getattr(c.content.parts[0], 'text', None) or ''
                    except (IndexError, AttributeError, KeyError, TypeError):
                        pass
                note_en = (note_en or '').strip()
                
                logger.info(f"Google AI note response received, length: {len(note_en)}")
                
                # Check if response is empty or too short
                if not note_en or len(note_en.strip()) < 10:
                    logger.error("Google AI returned an empty or too short note")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Google AI returned an empty or invalid note. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for note generation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'success': False, 'message': 'Groq API settings not configured'}, status=500)
            if not getattr(groq_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Groq model not selected in API settings'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                note_en = response.choices[0].message.content
                
                logger.info(f"Groq AI note response received, length: {len(note_en)}")
                
                # Check if response is empty or too short
                if not note_en or len(note_en.strip()) < 10:
                    logger.error("Groq AI returned an empty or too short note")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Groq AI returned an empty or invalid note. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for note generation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'success': False, 'message': 'DeepSeek API settings not configured'}, status=500)
            if not getattr(deepseek_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'DeepSeek model not selected in API settings'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates concise notes with additional recommendations for vulnerabilities."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                note_en = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI note response received, length: {len(note_en)}")
                
                # Check if response is empty or too short
                if not note_en or len(note_en.strip()) < 10:
                    logger.error("DeepSeek AI returned an empty or too short note")
                    return JsonResponse({
                        'success': False, 
                        'message': 'DeepSeek AI returned an empty or invalid note. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for note generation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'message': 'Claude API settings not configured'}, status=500)
            if not getattr(claude_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Claude model not selected in API settings'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                note_en = (response.content[0].text if response.content else None) or ''
                logger.info(f"Claude AI note response received, length: {len(note_en)}")
                
                # Check if response is empty or too short
                if not note_en or len(note_en.strip()) < 10:
                    logger.error("Claude AI returned an empty or too short note")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Claude AI returned an empty or invalid note. Please try again.'
                    }, status=400)
            except Exception as e:
                if AnthropicNotFoundError is not None and type(e) == AnthropicNotFoundError:
                    err_msg = str(e)
                    if 'model' in err_msg.lower() and ('not_found' in err_msg.lower() or '404' in err_msg):
                        friendly = (
                            'The selected Claude model was not found (it may have been deprecated). '
                            'Please select a different model in AI API settings.'
                        )
                    else:
                        friendly = err_msg
                    logger.error(f"Error using Claude AI for note generation: {err_msg}", exc_info=True)
                    return JsonResponse({'success': False, 'message': friendly}, status=400)
                err_msg = str(e)
                if 'not_found' in err_msg.lower() and 'model' in err_msg.lower():
                    friendly = (
                        'The selected Claude model was not found (it may have been deprecated). '
                        'Please select a different model in AI API settings.'
                    )
                    logger.error(f"Error using Claude AI for note generation: {err_msg}", exc_info=True)
                    return JsonResponse({'success': False, 'message': friendly}, status=400)
                logger.error(f"Error using Claude AI for note generation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Claude AI: {str(e)}'}, status=500)

        # Ensure we have a string before post-processing
        note_en = (note_en or '').strip()
        # Remove the introductory phrase if it exists
        note_en = re.sub(r'^(Here\'s a brief note with additional recommendations and considerations:\s*)?(Note:\s*)?',
                         '', note_en, flags=re.IGNORECASE).strip()

        # Translate to all configured form languages (uk, ru, de, etc.); always include note_en
        try:
            translated = _translate_to_form_languages(note_en, source_lang='en')
        except Exception as tr_err:
            logger.warning(f"Note translation failed, using English only: {tr_err}")
            translated = {}
        if 'en' not in translated:
            translated['en'] = note_en
        response_data = {'success': True, **{f'note_{lang}': (val or '') for lang, val in translated.items()}}

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in generate_note_ai: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def generate_description_ai(request):
    try:
        data = json.loads(request.body)
        vulnerability = _get_source_value(data, 'vulnerability') or data.get('vulnerability_en', '')
        scope = _get_source_value(data, 'scope') or data.get('scope_en', '')
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for description generation: {ai_provider}")

        prompt = f"""Based on the following vulnerability information, provide a detailed description:

        Scope: {scope}
        Vulnerability: {vulnerability}

        Please provide a comprehensive description that includes:
        1. An explanation of the vulnerability principle for this scope
        2. Methods of exploiting this vulnerability
        3. Potential impacts of this vulnerability
        4. Common scenarios where this vulnerability might be found

        Provide the description in a clear, concise manner suitable for security professionals.
        """

        description_en = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'success': False, 'message': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                description_en = response.text
                
                logger.info(f"Google AI description response received, length: {len(description_en)}")
                
                # Check if response is empty or too short
                if not description_en or len(description_en.strip()) < 20:
                    logger.error("Google AI returned an empty or too short description")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Google AI returned an empty or invalid description. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for description: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'success': False, 'message': 'Groq API settings not configured'}, status=500)
            if not getattr(groq_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Groq model not selected in API settings'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                description_en = response.choices[0].message.content
                
                logger.info(f"Groq AI description response received, length: {len(description_en)}")
                
                # Check if response is empty or too short
                if not description_en or len(description_en.strip()) < 20:
                    logger.error("Groq AI returned an empty or too short description")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Groq AI returned an empty or invalid description. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for description: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'success': False, 'message': 'DeepSeek API settings not configured'}, status=500)
            if not getattr(deepseek_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'DeepSeek model not selected in API settings'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates detailed descriptions for vulnerabilities."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                description_en = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI description response received, length: {len(description_en)}")
                
                # Check if response is empty or too short
                if not description_en or len(description_en.strip()) < 20:
                    logger.error("DeepSeek AI returned an empty or too short description")
                    return JsonResponse({
                        'success': False, 
                        'message': 'DeepSeek AI returned an empty or invalid description. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for description: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'message': 'Claude API settings not configured'}, status=500)
            if not getattr(claude_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Claude model not selected in API settings'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                description_en = response.content[0].text
                logger.info(f"Claude AI description response received, length: {len(description_en)}")
                
                # Check if response is empty or too short
                if not description_en or len(description_en.strip()) < 20:
                    logger.error("Claude AI returned an empty or too short description")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Claude AI returned an empty or invalid description. Please try again.'
                    }, status=400)
            except Exception as e:
                logger.error(f"Error using Claude AI for description: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Claude AI: {str(e)}'}, status=500)

        # Translate to all configured form languages (uk, ru, de, etc.)
        translated = _translate_to_form_languages(description_en, source_lang='en')
        response_data = {'success': True, **{f'description_{lang}': val for lang, val in translated.items()}}

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in generate_description_ai: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)




def get_asset_groups(request):
    from django.utils import translation
    language = request.GET.get('language', get_language())
    if language:
        translation.activate(language[:2].lower())

    groups = [
        {'id': g.id, 'localized_name': g.get_name()}
        for g in AssetGroup.objects.all()
    ]
    return JsonResponse({'groups': groups})





def get_asset_groups_and_types(request):
    from django.utils import translation
    language = request.GET.get('language', get_language())
    if language:
        translation.activate(language[:2].lower())

    # Get only groups and types that have associated vulnerabilities
    used_groups = set(Vulnerability.objects.values_list('asset_group_id', flat=True).distinct())
    used_types = set(Vulnerability.objects.values_list('asset_type_id', flat=True).distinct())

    groups = AssetGroup.objects.all()
    data = []

    for group in groups:
        if group.id in used_groups:
            group_data = {
                'id': group.id,
                'name': group.get_name(),
                'types': []
            }

            types = AssetType.objects.filter(group=group)
            for asset_type in types:
                if asset_type.id in used_types:
                    group_data['types'].append({
                        'id': asset_type.id,
                        'name': asset_type.get_name()
                    })

            if group_data['types']:
                data.append(group_data)

    return JsonResponse({'groups': data})




@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def analyze_multiply_threats_ai(request, vulnerability_id):
    try:
        vulnerability = Vulnerability.objects.get(id=vulnerability_id)
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for multiple threat analysis: {ai_provider}")

        # Build prompt from all configured languages (dynamic: uk, ru, en, de, etc.)
        from .vulnerability_utils import get_vulnerability_form_languages
        def _vuln_field(prefix):
            parts = []
            for code, name in get_vulnerability_form_languages():
                val = vulnerability.get_translated_value(prefix, code) or ''
                if val:
                    parts.append(f"{name}: {str(val)[:200]}{'...' if len(str(val)) > 200 else ''}")
            return ' / '.join(parts) if parts else '-'

        prompt = f"""Analyze the following vulnerability information and determine which threats from the existing list are most relevant. The vulnerability details are:

Asset Group: {vulnerability.asset_group}
Asset Type: {vulnerability.asset_type}
Scope: {_vuln_field('scope')}
Vulnerability: {_vuln_field('vulnerability')}
Risk Mitigation Controls: {_vuln_field('risk_mitigation_controls')}
PCI DSS Requirement: {_vuln_field('pci_dss_requirement')}
ISO27001 Requirement: {_vuln_field('iso27001_requirement')}
Note: {_vuln_field('note')}

Based on this information, which of the following threats are most relevant? Please return only the IDs of the relevant threats.

Existing Threats:
"""

        # Get all existing threats
        threats = Threat.objects.all()
        for threat in threats:
            prompt += f"{threat.id}: {threat.get_name_by_language('uk')} / {threat.get_name_by_language('ru')} / {threat.get_name_by_language('en')}\n"

        ai_response = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings:
                return JsonResponse({'success': False, 'message': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)
                
                response = model.generate_content(prompt)
                ai_response = response.text
                
                logger.info(f"Google AI multiple threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("Google AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Google AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for multiple threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'success': False, 'message': 'Groq API settings not configured'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"Groq AI multiple threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("Groq AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Groq AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for multiple threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'success': False, 'message': 'DeepSeek API settings not configured'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies relevant threats for vulnerabilities."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI multiple threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("DeepSeek AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'DeepSeek AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for risk mitigation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'message': 'Claude API settings not configured'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                ai_response = response.content[0].text
                logger.info(f"Claude AI multiple threat analysis response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 5:
                    logger.error("Claude AI returned an empty or too short response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Claude AI returned an empty or invalid response. Please try again.'
                    }, status=400)
            except Exception as e:
                logger.error(f"Error using Claude AI for multiple threat analysis: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Claude AI: {str(e)}'}, status=500)

        # Parse the response to get threat IDs
        threat_ids = [int(id) for id in re.findall(r'\b\d+\b', ai_response)]
        
        if not threat_ids:
            logger.warning("No threat IDs found in AI response")
            return JsonResponse({
                'success': False, 
                'message': f'No threat IDs could be identified in the {ai_provider.capitalize()} AI response. Please try again.'
            }, status=400)

        # Update the vulnerability with the new threats
        relevant_threats = Threat.objects.filter(id__in=threat_ids)
        vulnerability.threats.set(relevant_threats)

        return JsonResponse({
            'success': True,
            'message': 'Threats analyzed and updated successfully',
            'threats': [{'id': t.id, 'name_uk': t.get_name_by_language('uk'), 'name_ru': t.get_name_by_language('ru'), 'name_en': t.get_name_by_language('en')} for t in relevant_threats]
        })

    except Vulnerability.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Vulnerability not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in analyze_multiply_threats_ai: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)




def parse_ai_response(response):
    vulnerabilities = []
    current_vuln = {}
    current_field = None

    for line in response.split('\n'):
        line = line.strip()
        if not line:
            if current_vuln:
                # Перевірка та заповнення відсутніх полів
                if not current_vuln.get('pci_dss_requirement'):
                    current_vuln['pci_dss_requirement'] = ["Requirements: None"]
                if not current_vuln.get('iso27001_requirement'):
                    current_vuln['iso27001_requirement'] = ["Requirements: None"]
                vulnerabilities.append(current_vuln)
                current_vuln = {}
            current_field = None
            continue

        if ':' in line:
            field, value = line.split(':', 1)
            field = field.strip().lower()
            value = value.strip()

            if field == 'vulnerability':
                current_vuln['vulnerability'] = value
            elif field == 'scope':
                current_vuln['scope'] = value
            elif field == 'description':
                current_vuln['description'] = value
            elif field == 'risk mitigation controls':
                current_vuln['risk_mitigation_controls'] = []
                current_field = 'risk_mitigation_controls'
            elif field == 'pci dss requirement':
                current_vuln['pci_dss_requirement'] = []
                current_field = 'pci_dss_requirement'
            elif field == 'iso27001 requirement':
                current_vuln['iso27001_requirement'] = []
                current_field = 'iso27001_requirement'
            elif field == 'note':
                current_vuln['note'] = value
        elif line.startswith('*') and current_field:
            current_vuln[current_field].append(line[1:].strip())
        elif current_field:
            current_vuln[current_field].append(line)

    # Обробка останньої вразливості
    if current_vuln:
        if not current_vuln.get('pci_dss_requirement'):
            current_vuln['pci_dss_requirement'] = ["Requirements: None"]
        if not current_vuln.get('iso27001_requirement'):
            current_vuln['iso27001_requirement'] = ["Requirements: None"]
        vulnerabilities.append(current_vuln)

    return vulnerabilities




@user_passes_test(can_add_risk_config)
@csrf_exempt
@require_POST
def save_generated_vulnerabilities(request):
    try:
        data = json.loads(request.body)
        asset_group_id = data.get('asset_group')
        asset_type_id = data.get('asset_type')
        vulnerabilities = data.get('vulnerabilities', [])
        
        logger.info(f"Saving generated vulnerabilities - Asset Group: {asset_group_id}, Asset Type: {asset_type_id}")
        logger.debug(f"Vulnerabilities data: {vulnerabilities}")
        
        if not asset_group_id or not asset_type_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters: asset_group and asset_type must be provided'
            }, status=400)
            
        if not vulnerabilities or not isinstance(vulnerabilities, list):
            return JsonResponse({
                'success': False,
                'error': 'No vulnerabilities provided or data is in incorrect format'
            }, status=400)
        
        try:
            asset_group = AssetGroup.objects.get(id=asset_group_id)
            asset_type = AssetType.objects.get(id=asset_type_id)
        except (AssetGroup.DoesNotExist, AssetType.DoesNotExist) as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid asset group or type: {str(e)}'
            }, status=400)

        saved_vulnerabilities = []
        errors = []

        from .vulnerability_utils import get_vulnerability_form_languages
        from .models import Vulnerability as VulnModel
        lang_codes = [code for code, _ in get_vulnerability_form_languages()]
        # Map logical field name to model attribute for default (en) value
        _field_to_attr = {'vulnerability': 'name'}
        def _model_attr(field, lang):
            if lang != 'en':
                return None
            return _field_to_attr.get(field, field)

        def _val(vuln_data, field, lang):
            return vuln_data.get(f'{field}_{lang}', vuln_data.get(field, '') if lang == 'en' else '') or ''

        for index, vuln_data in enumerate(vulnerabilities):
            try:
                kwargs = {'asset_group': asset_group, 'asset_type': asset_type}
                extra = {}
                for field in VulnModel.TRANSLATABLE_FIELDS:
                    for lang in lang_codes:
                        val = _val(vuln_data, field, lang)
                        model_attr = _model_attr(field, lang)
                        if model_attr is not None:
                            kwargs[model_attr] = val
                        else:
                            if field not in extra:
                                extra[field] = {}
                            extra[field][lang] = val
                if extra:
                    kwargs['extra_translations'] = extra

                check_vuln = vuln_data.get('vulnerability_en', vuln_data.get('vulnerability', ''))
                check_scope = vuln_data.get('scope_en', vuln_data.get('scope', ''))
                logger.debug(f"Processing vulnerability {index+1}: {(check_vuln or '')[:30]}...")

                if not Vulnerability.objects.filter(
                    asset_type=asset_type,
                    name=check_vuln,
                    scope=check_scope
                ).exists():
                    vulnerability = Vulnerability.objects.create(**kwargs)
                    saved_vulnerabilities.append(vulnerability.id)
                    logger.info(f"Created new vulnerability ID {vulnerability.id}")
                else:
                    error_msg = f"Vulnerability {index+1} already exists in the database"
                    logger.info(error_msg)
                    errors.append(error_msg)
            except Exception as create_error:
                error_msg = f"Error creating vulnerability {index+1}: {str(create_error)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                continue

        response_data = {
            'success': len(saved_vulnerabilities) > 0,
            'saved_vulnerabilities': saved_vulnerabilities,
            'message': f'{len(saved_vulnerabilities)} new vulnerabilities saved successfully'
        }
        
        if errors:
            response_data['errors'] = errors
            if not saved_vulnerabilities:
                response_data['message'] = 'Failed to save any vulnerabilities'
                
        return JsonResponse(response_data)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in save_generated_vulnerabilities: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': f'Invalid JSON data: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in save_generated_vulnerabilities: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)

@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def generate_risk_mitigation_ai(request):
    try:
        data = json.loads(request.body)
        vulnerability = _get_source_value(data, 'vulnerability') or data.get('vulnerability_en', '')
        scope = _get_source_value(data, 'scope') or data.get('scope_en', '')
        description = _get_source_value(data, 'description') or data.get('description_en', '')
        threats_raw = data.get('threats', [])
        threats_str = ', '.join(str(t) for t in (threats_raw if isinstance(threats_raw, (list, tuple)) else []))
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for risk mitigation generation: {ai_provider}")

        prompt = f"""Based on the following vulnerability information, provide detailed risk mitigation controls:

        Scope: {scope}
        Vulnerability: {vulnerability}
        Description: {description}
        Threats: {threats_str}

        Please provide risk mitigation controls that include:
        1. Technical controls
        2. Administrative controls
        3. Preventive measures
        4. Detective measures
        5. Corrective actions

        Format the controls as a bulleted list with clear and actionable items. Start directly with the bullet points, do not include any introductory text or headings. Each control should be specific and directly address the vulnerability and associated threats.
        """

        risk_mitigation_en = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'success': False, 'message': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                risk_mitigation_en = response.text
                
                logger.info(f"Google AI risk mitigation response received, length: {len(risk_mitigation_en)}")
                
                # Check if response is empty or too short
                if not risk_mitigation_en or len(risk_mitigation_en.strip()) < 20:
                    logger.error("Google AI returned an empty or too short risk mitigation")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Google AI returned an empty or invalid risk mitigation. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for risk mitigation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings or not groq_settings.model_name:
                return JsonResponse({'success': False, 'message': 'Groq API settings not configured'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                risk_mitigation_en = response.choices[0].message.content
                
                logger.info(f"Groq AI risk mitigation response received, length: {len(risk_mitigation_en)}")
                
                # Check if response is empty or too short
                if not risk_mitigation_en or len(risk_mitigation_en.strip()) < 20:
                    logger.error("Groq AI returned an empty or too short risk mitigation")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Groq AI returned an empty or invalid risk mitigation. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for risk mitigation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'success': False, 'message': 'DeepSeek API settings not configured'}, status=500)
            if not getattr(deepseek_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'DeepSeek model not selected in API settings'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies relevant risk mitigation controls for vulnerabilities."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                risk_mitigation_en = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI risk mitigation response received, length: {len(risk_mitigation_en)}")
                
                # Check if response is empty or too short
                if not risk_mitigation_en or len(risk_mitigation_en.strip()) < 20:
                    logger.error("DeepSeek AI returned an empty or too short risk mitigation")
                    return JsonResponse({
                        'success': False, 
                        'message': 'DeepSeek AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for risk mitigation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'message': 'Claude API settings not configured'}, status=500)
            if not getattr(claude_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Claude model not selected in API settings'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                risk_mitigation_en = response.content[0].text
                logger.info(f"Claude AI risk mitigation response received, length: {len(risk_mitigation_en)}")
                
                # Check if response is empty or too short
                if not risk_mitigation_en or len(risk_mitigation_en.strip()) < 20:
                    logger.error("Claude AI returned an empty or too short risk mitigation")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Claude AI returned an empty or invalid risk mitigation. Please try again.'
                    }, status=400)
            except Exception as e:
                logger.error(f"Error using Claude AI for risk mitigation: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Claude AI: {str(e)}'}, status=500)

        # Remove common introductory phrases
        introductory_phrases = [
            "Based on the provided vulnerability information,",
            "Here is a comprehensive list of risk mitigation controls:",
            "Here are the recommended risk mitigation controls:",
            "Recommended risk mitigation controls:",
            "The following risk mitigation controls are recommended:",
            "Risk mitigation controls:"
        ]

        for phrase in introductory_phrases:
            risk_mitigation_en = risk_mitigation_en.replace(phrase, "").strip()

        # Remove any remaining lines that don't start with a bullet point or number
        risk_mitigation_lines = risk_mitigation_en.split('\n')
        cleaned_lines = []
        for line in risk_mitigation_lines:
            line = line.strip()
            if line and (line.startswith('•') or line.startswith('-') or line.startswith('*') or
                         (line[0].isdigit() and line[1] == '.')):
                cleaned_lines.append(line)

        risk_mitigation_en = '\n'.join(cleaned_lines)

        # Translate to all configured form languages (uk, ru, de, etc.)
        translated = _translate_to_form_languages(risk_mitigation_en, source_lang='en')
        response_data = {'success': True, **{f'risk_mitigation_{lang}': val for lang, val in translated.items()}}

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in generate_risk_mitigation_ai: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def search_pcidss_requirement(request):
    try:
        data = json.loads(request.body)
        vulnerability_en = _get_source_value(data, 'vulnerability') or data.get('vulnerability_en', '')
        description_en = _get_source_value(data, 'description') or data.get('description_en', '')
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for PCI DSS requirement search: {ai_provider}")

        # Get all categories and requirements
        categories = PCIDSSCategory.objects.all()
        requirements = PCIDSSRequirement.objects.all()

        # Prepare category and requirement lists for AI (models use get_name/get_title, not category_en/title_en)
        category_list = "\n".join([f"{cat.id}. {(cat.get_name('en') or getattr(cat, 'name', '') or getattr(cat, 'name_local', '') or '')}" for cat in categories])
        requirement_list = "\n".join([f"{req.id}. {req.requirement_number}: {(req.get_title('en') or getattr(req, 'title', '') or '')}" for req in requirements])

        # Prepare the prompt for AI
        prompt = f"""Given the following vulnerability information, identify the most relevant PCI DSS requirement(s):

        Vulnerability: {vulnerability_en}
        Description: {description_en}

        First, select the most relevant category or categories from the following list:
        {category_list}

        Then, select the most relevant requirement(s) from the following list:
        {requirement_list}

        Please return your response in the following format:
        Category ID(s): [selected category id(s), separated by commas if multiple]
        Requirement ID(s): [selected requirement id(s), separated by commas if multiple]
        Explanation: [brief explanation of your choice(s)]

        If no relevant requirements are found, please state "No relevant requirements found." in the Requirement ID(s) field.
        """

        ai_response = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'success': False, 'message': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                ai_response = response.text
                
                logger.info(f"Google AI PCI DSS requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("Google AI returned an empty or too short PCI DSS requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Google AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for PCI DSS requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'success': False, 'message': 'Groq API settings not configured'}, status=500)
            if not getattr(groq_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Groq model not selected in API settings'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"Groq AI PCI DSS requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("Groq AI returned an empty or too short PCI DSS requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Groq AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for PCI DSS requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Groq AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'success': False, 'message': 'DeepSeek API settings not configured'}, status=500)
            if not getattr(deepseek_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'DeepSeek model not selected in API settings'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies relevant PCI DSS requirements for vulnerabilities."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI PCI DSS requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("DeepSeek AI returned an empty or too short PCI DSS requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'DeepSeek AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for PCI DSS requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'message': 'Claude API settings not configured'}, status=500)
            if not getattr(claude_settings, 'model_name', None):
                return JsonResponse({'success': False, 'message': 'Claude model not selected in API settings'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                ai_response = response.content[0].text
                logger.info(f"Claude AI PCI DSS requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("Claude AI returned an empty or too short PCI DSS requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Claude AI returned an empty or invalid response. Please try again.'
                    }, status=400)
            except Exception as e:
                logger.error(f"Error using Claude AI for PCI DSS requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Claude AI: {str(e)}'}, status=500)

        # Parse the response
        lines = ai_response.strip().split('\n')
        
        # Make sure we have at least 2 lines (Category IDs and Requirement IDs)
        if len(lines) < 2:
            logger.error(f"AI response does not have the expected format: {ai_response}")
            return JsonResponse({
                'success': False,
                'message': f'The {ai_provider.capitalize()} AI response does not have the expected format. Please try again.'
            }, status=400)
            
        # Find the line with "Category ID" and "Requirement ID"
        category_line = None
        requirement_line = None
        
        for line in lines:
            if "category id" in line.lower():
                category_line = line
            if "requirement id" in line.lower():
                requirement_line = line
        
        if not category_line or not requirement_line:
            logger.error(f"Could not find Category ID or Requirement ID lines in AI response: {ai_response}")
            return JsonResponse({
                'success': False,
                'message': f'The {ai_provider.capitalize()} AI response does not have the expected format. Please try again.'
            }, status=400)
            
        # Extract category IDs and requirement IDs
        category_ids = re.findall(r'\d+', category_line.split(':')[1] if ':' in category_line else '')
        requirement_ids_text = requirement_line.split(':')[1].strip() if ':' in requirement_line else ''

        if "no relevant requirements found" in requirement_ids_text.lower():
            return JsonResponse({
                'success': True,
                'message': 'No relevant PCI DSS requirements found.'
            })

        requirement_ids = re.findall(r'\d+', requirement_ids_text)
        
        if not requirement_ids:
            logger.warning(f"No requirement IDs found in AI response: {ai_response}")
            return JsonResponse({
                'success': True,
                'message': 'No relevant PCI DSS requirements found.'
            })

        # Retrieve the selected requirements
        selected_requirements = PCIDSSRequirement.objects.filter(id__in=requirement_ids)

        # Build base requirements (model uses get_title(lang), not title_en/title_uk/title_ru)
        requirements_en = '\n'.join(f"{req.requirement_number}: {(req.get_title('en') or getattr(req, 'title', '') or '')}" for req in selected_requirements)
        requirements_uk = '\n'.join(f"{req.requirement_number}: {(req.get_title('uk') or getattr(req, 'title', '') or '')}" for req in selected_requirements)
        requirements_ru = '\n'.join(f"{req.requirement_number}: {(req.get_title('ru') or getattr(req, 'title', '') or '')}" for req in selected_requirements)

        # Add translations for additional form languages (de, fr, etc.)
        from .vulnerability_utils import get_vulnerability_form_languages
        response_data = {'success': True, 'requirements_en': requirements_en, 'requirements_uk': requirements_uk, 'requirements_ru': requirements_ru}
        if requirements_en:
            trans = _translate_to_form_languages(requirements_en, source_lang='en')
            for code, _ in get_vulnerability_form_languages():
                if code not in ('uk', 'ru', 'en'):
                    response_data[f'requirements_{code}'] = trans.get(code, '')
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in search_pcidss_requirement: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@require_GET
def check_ai_provider(request):
    """
    Check if the specified AI provider is configured.
    """
    provider = request.GET.get('provider', 'claude')
    
    try:
        if provider == 'google':
            from app_ai.models import APISettingsGoogle
            settings = APISettingsGoogle.objects.first()
            configured = settings is not None and settings.api_key
        elif provider == 'groq':
            from app_ai.models import APISettingsGroq
            settings = APISettingsGroq.objects.first()
            configured = settings is not None and settings.api_key
        elif provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            settings = APISettingsDeepSeek.objects.first()
            configured = settings is not None and settings.api_key
        else:  # Default to Claude
            from app_ai.models import APISettingsClaude
            settings = APISettingsClaude.objects.first()
            configured = settings is not None and settings.api_key
        
        return JsonResponse({
            'provider': provider,
            'configured': configured
        })
    except Exception as e:
        logger.error(f"Error checking AI provider configuration: {str(e)}", exc_info=True)
        return JsonResponse({
            'provider': provider,
            'configured': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_POST
def search_iso27001_requirement(request):
    try:
        data = json.loads(request.body)
        vulnerability_en = _get_source_value(data, 'vulnerability') or data.get('vulnerability_en', '')
        description_en = _get_source_value(data, 'description') or data.get('description_en', '')
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for ISO 27001 requirement search: {ai_provider}")

        controls = ISO27002Control.objects.all()
        themes = ISO27002Theme.objects.all()

        prompt = f"""Given the following vulnerability information, identify the most relevant ISO 27002 controls:

        Vulnerability: {vulnerability_en}
        Description: {description_en}

        Available controls:
        {', '.join([f"{control.control_number}: {(control.get_title('en') or getattr(control, 'title', '') or '')}" for control in controls])}

        Please return your response in the following format:
        Control Numbers: [selected control numbers, separated by commas if multiple]
        Brief Explanation: [why these controls are relevant]
        """

        ai_response = ""
        
        # Use the appropriate AI provider
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                return JsonResponse({'success': False, 'message': 'Google API settings not configured'}, status=500)
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_settings.api_key)
                model = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
                
                response = model.generate_content(prompt)
                ai_response = response.text
                
                logger.info(f"Google AI ISO 27001 requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("Google AI returned an empty or too short ISO 27001 requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Google AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Google AI for ISO 27001 requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Google AI: {str(e)}'}, status=500)
        
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings:
                return JsonResponse({'success': False, 'message': 'Groq API settings not configured'}, status=500)
            
            try:
                from groq import Groq
                client = Groq(api_key=groq_settings.api_key)
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=groq_settings.model_name.model_id,  # Use model_id instead of model_name
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"Groq AI ISO 27001 requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("Groq AI returned an empty or too short ISO 27001 requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Groq AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using Groq AI for ISO 27001 requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Groq AI: {str(e)}'}, status=500)
                
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings:
                return JsonResponse({'success': False, 'message': 'DeepSeek API settings not configured'}, status=500)
            
            try:
                import openai
                client = openai.OpenAI(
                    api_key=deepseek_settings.api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
                response = client.chat.completions.create(
                    model=deepseek_settings.model_name.model_id,  # Use model_id instead of model_name
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies relevant ISO 27002 controls for vulnerabilities."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=deepseek_settings.temperature,
                    max_tokens=deepseek_settings.max_tokens,
                    top_p=deepseek_settings.top_p,
                    frequency_penalty=deepseek_settings.frequency_penalty,
                    presence_penalty=deepseek_settings.presence_penalty
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"DeepSeek AI ISO 27001 requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("DeepSeek AI returned an empty or too short ISO 27001 requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'DeepSeek AI returned an empty or invalid response. Please try again.'
                    }, status=400)
                    
            except Exception as e:
                logger.error(f"Error using DeepSeek AI for ISO 27001 requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using DeepSeek AI: {str(e)}'}, status=500)
        
        else:  # Default to Claude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings:
                return JsonResponse({'success': False, 'message': 'Claude API settings not configured'}, status=500)

            try:
                client = Anthropic(api_key=claude_settings.api_key)
                response = client.messages.create(
                    model=claude_settings.model_name.model_id,  # Use model_id instead of model_name
                    max_tokens=claude_settings.max_tokens,
                    temperature=claude_settings.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                ai_response = response.content[0].text
                logger.info(f"Claude AI ISO 27001 requirement search response received, length: {len(ai_response)}")
                
                # Check if response is empty or too short
                if not ai_response or len(ai_response.strip()) < 10:
                    logger.error("Claude AI returned an empty or too short ISO 27001 requirement search response")
                    return JsonResponse({
                        'success': False, 
                        'message': 'Claude AI returned an empty or invalid response. Please try again.'
                    }, status=400)
            except Exception as e:
                logger.error(f"Error using Claude AI for ISO 27001 requirement search: {str(e)}", exc_info=True)
                return JsonResponse({'success': False, 'message': f'Error using Claude AI: {str(e)}'}, status=500)

        # Parse control numbers from response
        control_numbers = re.findall(r'[\d\.]+', ai_response.split('\n')[0])
        
        if not control_numbers:
            logger.warning(f"No control numbers found in AI response: {ai_response}")
            return JsonResponse({
                'success': True,
                'message': 'No relevant ISO 27001 controls found.'
            })

        # Get the matching controls
        matched_controls = ISO27002Control.objects.filter(control_number__in=control_numbers)

        # Build base requirements (model uses get_title/get_control_description(lang), not title_en/control_description_en)
        controls_en = '\n\n'.join(f"{c.control_number}: {(c.get_title('en') or getattr(c, 'title', '') or '')}:\n{(c.get_control_description('en') or getattr(c, 'control_description', '') or '')}" for c in matched_controls)
        controls_uk = '\n\n'.join(f"{c.control_number}: {(c.get_title('uk') or getattr(c, 'title', '') or '')}:\n{(c.get_control_description('uk') or getattr(c, 'control_description', '') or '')}" for c in matched_controls)
        controls_ru = '\n\n'.join(f"{c.control_number}: {(c.get_title('ru') or getattr(c, 'title', '') or '')}:\n{(c.get_control_description('ru') or getattr(c, 'control_description', '') or '')}" for c in matched_controls)

        response_data = {'success': True, 'requirements_en': controls_en, 'requirements_uk': controls_uk, 'requirements_ru': controls_ru}
        # Add translations for additional form languages (de, fr, etc.)
        from .vulnerability_utils import get_vulnerability_form_languages
        if controls_en:
            trans = _translate_to_form_languages(controls_en, source_lang='en')
            for code, _ in get_vulnerability_form_languages():
                if code not in ('uk', 'ru', 'en'):
                    response_data[f'requirements_{code}'] = trans.get(code, '')
        logger.info(f"Found {len(matched_controls)} ISO 27001 controls using {ai_provider.capitalize()} AI")
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in search_iso27001_requirement: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def _country_code_to_lang():
    """Build map country_code (upper) -> language code from LANGUAGE_COUNTRY_MAP."""
    from .models import LANGUAGE_COUNTRY_MAP
    out = {}
    for lang, codes in LANGUAGE_COUNTRY_MAP.items():
        for cc in codes:
            out[(cc or '').upper()] = lang
    return out


# Language code -> display name for AI translation prompts
_LANG_DISPLAY_NAMES = {
    'uk': 'Ukrainian', 'ru': 'Russian', 'en': 'English', 'pl': 'Polish', 'de': 'German',
    'fr': 'French', 'es': 'Spanish', 'it': 'Italian', 'pt': 'Portuguese', 'nl': 'Dutch',
    'cs': 'Czech', 'sk': 'Slovak', 'ro': 'Romanian', 'bg': 'Bulgarian', 'lt': 'Lithuanian',
}


def _translate_text_with_ai(text, target_lang_code, request):
    """Translate text using the configured AI provider. Returns translated string or original on failure."""
    if not text or not str(text).strip():
        return ''
    lang_name = _LANG_DISPLAY_NAMES.get(target_lang_code, target_lang_code)
    prompt = f"""Translate the following text from English to {lang_name}. Return only the translation, no explanation or quotes.

Text:
{str(text).strip()}"""
    ai_provider = request.GET.get('provider', 'claude')
    try:
        if ai_provider == 'google':
            from app_ai.models import APISettingsGoogle
            settings = APISettingsGoogle.objects.first()
            if not settings or not getattr(settings, 'model_name', None):
                raise ValueError('Google API settings not configured')
            import google.generativeai as genai
            genai.configure(api_key=settings.api_key)
            model = genai.GenerativeModel(settings.model_name.model_id)
            response = model.generate_content(prompt)
            out = getattr(response, 'text', None) or ''
            if not out and getattr(response, 'candidates', None):
                try:
                    out = response.candidates[0].content.parts[0].text
                except (IndexError, AttributeError, TypeError):
                    pass
            return (out or str(text)).strip()
        elif ai_provider == 'groq':
            from app_ai.models import APISettingsGroq
            from groq import Groq
            settings = APISettingsGroq.objects.first()
            if not settings or not getattr(settings, 'model_name', None):
                raise ValueError('Groq API settings not configured')
            client = Groq(api_key=settings.api_key)
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=settings.model_name.model_id,
            )
            return (response.choices[0].message.content or str(text)).strip()
        elif ai_provider == 'deepseek':
            from app_ai.models import APISettingsDeepSeek
            import openai
            settings = APISettingsDeepSeek.objects.first()
            if not settings or not getattr(settings, 'model_name', None):
                raise ValueError('DeepSeek API settings not configured')
            client = openai.OpenAI(
                api_key=settings.api_key,
                base_url="https://api.deepseek.com/v1"
            )
            response = client.chat.completions.create(
                model=settings.model_name.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=getattr(settings, 'temperature', 0.3),
                max_tokens=getattr(settings, 'max_tokens', 2048),
            )
            return (response.choices[0].message.content or str(text)).strip()
        else:
            from app_ai.models import APISettingsClaude
            settings = APISettingsClaude.objects.first()
            if not settings or not getattr(settings, 'model_name', None):
                raise ValueError('Claude API settings not configured')
            client = Anthropic(api_key=settings.api_key)
            response = client.messages.create(
                model=settings.model_name.model_id,
                max_tokens=getattr(settings, 'max_tokens', 4096),
                temperature=getattr(settings, 'temperature', 0.3),
                messages=[{"role": "user", "content": prompt}]
            )
            out = (response.content[0].text if response.content else None) or ''
            return out.strip() or str(text)
    except Exception as e:
        logger.warning(f"AI translation failed: {e}")
        return str(text)


@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def translate_vulnerability_ai_preview(request):
    """Translate vulnerability fields to one country's language; return JSON preview without saving.
    Request body: vulnerability_id, country_id, translation_method ('google' | 'ai').
    For AI, provider from GET param (claude, google, groq, deepseek)."""
    from app_conf.models import Country
    try:
        data = json.loads(request.body)
        vulnerability_id = data.get('vulnerability_id')
        country_id = data.get('country_id')
        translation_method = (data.get('translation_method') or 'google').lower()
        if translation_method not in ('google', 'ai'):
            translation_method = 'google'
        if not vulnerability_id or not country_id:
            return JsonResponse({'success': False, 'message': 'vulnerability_id and country_id required'}, status=400)
        vulnerability = Vulnerability.objects.get(id=vulnerability_id)
        country = Country.objects.get(id=country_id)
        code_to_lang = _country_code_to_lang()
        target_lang = code_to_lang.get((country.code or '').upper())
        if not target_lang:
            return JsonResponse({'success': False, 'message': 'No language mapping for this country'}, status=400)
        source_lang = 'en'
        field_map = [
            ('vulnerability', 'name_local'),
            ('description', 'description'),
            ('scope', 'scope'),
            ('risk_mitigation_controls', 'risk_mitigation_controls'),
            ('pci_dss_requirement', 'pci_dss_requirement'),
            ('iso27001_requirement', 'iso27001_requirement'),
            ('note', 'note'),
        ]
        result = {}
        for form_field, out_key in field_map:
            raw = vulnerability.get_translated_value(form_field, source_lang) or ''
            if isinstance(raw, str) and ('UK:' in raw or 'RU:' in raw):
                raw = raw.split('UK:')[0].split('RU:')[0].strip()
            if raw and len(str(raw).strip()) >= 1:
                if translation_method == 'ai':
                    result[out_key] = _translate_text_with_ai(raw, target_lang, request)
                else:
                    result[out_key] = _translate_text_to_lang(raw, source_lang=source_lang, target_lang=target_lang)
            else:
                result[out_key] = ''
        return JsonResponse({'success': True, 'preview': result})
    except Vulnerability.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Vulnerability not found'}, status=404)
    except Country.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Country not found'}, status=404)
    except Exception as e:
        logger.exception("translate_vulnerability_ai_preview")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def translate_threat_preview(request):
    """Translate threat fields (name, description, risks) to one country's language; return JSON preview without saving."""
    from app_conf.models import Country
    try:
        data = json.loads(request.body)
        threat_id = data.get('threat_id')
        country_id = data.get('country_id')
        translation_method = (data.get('translation_method') or 'google').lower()
        if translation_method not in ('google', 'ai'):
            translation_method = 'google'
        if not threat_id or not country_id:
            return JsonResponse({'success': False, 'message': 'threat_id and country_id required'}, status=400)
        threat = Threat.objects.get(id=threat_id)
        country = Country.objects.get(id=country_id)
        code_to_lang = _country_code_to_lang()
        target_lang = code_to_lang.get((country.code or '').upper())
        if not target_lang:
            return JsonResponse({'success': False, 'message': 'No language mapping for this country'}, status=400)
        source_lang = 'en'
        field_map = [('name', 'name_local'), ('description', 'description'), ('risks', 'risks')]
        result = {}
        for form_field, out_key in field_map:
            # Default English: use main model fields when get_translated_value is empty
            raw = threat.get_translated_value(form_field, source_lang) or getattr(threat, form_field, None) or ''
            raw = (raw and str(raw).strip()) or ''
            if raw:
                if translation_method == 'ai':
                    result[out_key] = _translate_text_with_ai(raw, target_lang, request)
                else:
                    result[out_key] = _translate_text_to_lang(raw, source_lang=source_lang, target_lang=target_lang)
            else:
                result[out_key] = ''
        return JsonResponse({'success': True, 'preview': result})
    except Threat.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Threat not found'}, status=404)
    except Country.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Country not found'}, status=404)
    except Exception as e:
        logger.exception("translate_threat_preview")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@user_passes_test(can_edit_risk_config)
@csrf_exempt
@require_POST
def translate_vulnerability_ai(request):
    try:
        data = json.loads(request.body)
        vulnerability_id = data.get('vulnerability_id')
        
        # Get the AI provider from query parameters, default to Claude
        ai_provider = request.GET.get('provider', 'claude')
        logger.info(f"Using AI provider for vulnerability translation: {ai_provider}")
        
        # Get the vulnerability
        vulnerability = Vulnerability.objects.get(id=vulnerability_id)

        from .vulnerability_utils import get_vulnerability_form_languages

        field_names = ['vulnerability', 'scope', 'description', 'risk_mitigation_controls', 'pci_dss_requirement', 'iso27001_requirement', 'note']
        target_langs = [code for code, _ in get_vulnerability_form_languages() if code != 'en']

        translated_fields = []
        skipped_fields = []
        errors = []
        translated_data = {}

        for field_name in field_names:
            try:
                en_value = vulnerability.get_translated_value(field_name, 'en') or ''
                if en_value:
                    if 'UK:' in en_value:
                        en_value = en_value.split('UK:')[0].strip()
                    if 'RU:' in en_value:
                        en_value = en_value.split('RU:')[0].strip()

                if not en_value or len(str(en_value).strip()) < 3:
                    logger.info(f"Skipping translation of empty or very short field: {field_name}")
                    skipped_fields.append(field_name)
                    continue

                # Translate to all target languages (uk, ru, de, etc.)
                translated = _translate_to_form_languages(en_value, source_lang='en')
                for lang in target_langs:
                    val = translated.get(lang)
                    if val:
                        vulnerability.set_translated_value(field_name, lang, val)
                        translated_data[f"{field_name}_{lang}"] = val

                translated_fields.append(field_name)
                logger.info(f"Translated {field_name} for vulnerability ID {vulnerability_id}")
            except Exception as field_error:
                logger.error(f"Error translating field {field_name}: {str(field_error)}", exc_info=True)
                errors.append(f"{field_name}: {str(field_error)}")
        
        # Save the vulnerability
        vulnerability.save()
        
        response_message = f'Vulnerability ID {vulnerability_id} translated successfully'
        if skipped_fields:
            response_message += f'. Skipped empty fields: {", ".join(skipped_fields)}'
        if errors:
            response_message += f'. Errors in fields: {", ".join(errors)}'
        
        return JsonResponse({
            'success': True,
            'message': response_message,
            'translated_fields': translated_fields,
            'skipped_fields': skipped_fields,
            'errors': errors,
            'translated_data': translated_data,
            'vulnerability_id': vulnerability_id
        })
        
    except Vulnerability.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Vulnerability not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in translate_vulnerability_ai: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
