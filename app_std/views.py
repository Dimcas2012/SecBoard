# SecBoard/app_std/views.py
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from .pcidss_view import *
from .pcidss_view import check_pcidss_access, check_pcidss_edit_access
from .ISO27002_view import *
from deep_translator import GoogleTranslator
import logging
from app_ai.models import APISettingsClaude, APISettingsGoogle, APISettingsDeepSeek
import anthropic
from anthropic import Anthropic
import openai
import google.generativeai as genai
import re
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import PCIDSSDocument
import json
import os
from django.conf import settings

logger = logging.getLogger(__name__)



logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")


def translate_text(text, source_lang, target_lang):
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    return translator.translate(text)


# Ініціалізація моделей AI
def init_google_ai():
    try:
        settings = APISettingsGoogle.objects.first()
        if not settings or not settings.model_name:
            logger.error("Google API settings not found in database")
            return None
        genai.configure(api_key=settings.api_key)
        model = genai.GenerativeModel(settings.model_name.model_id)  # Use model_id instead of model_name
        return model
    except Exception as e:
        logger.error(f"Error initializing Google AI: {str(e)}")
        return None

def init_claude_ai():
    try:
        settings = APISettingsClaude.objects.first()
        if not settings:
            logger.error("Claude API settings not found in database")
            return None, None
        anthropic = Anthropic(api_key=settings.api_key)
        return anthropic, settings.model_name
    except Exception as e:
        logger.error(f"Error initializing Claude AI: {str(e)}")
        return None, None

# Глобальні змінні для моделей
google_model = init_google_ai()
claude_model, claude_model_name = init_claude_ai()


def format_requirement_data(req):
    """Format requirement data for response"""
    try:
        return {
            'id': req.id,
            'requirement_number': req.requirement_number,
            'category': {
                'en': req.category.get_name('en'),
                'uk': req.category.get_name('uk'),
                'ru': req.category.get_name('ru')
            } if req.category else {},
            'title': {
                'en': req.get_title('en'),
                'uk': req.get_title('uk'),
                'ru': req.get_title('ru')
            },
            'description': {
                'en': req.get_description('en'),
                'uk': req.get_description('uk'),
                'ru': req.get_description('ru')
            },
            'testing_procedures': {
                'en': req.get_testing_procedures('en'),
                'uk': req.get_testing_procedures('uk'),
                'ru': req.get_testing_procedures('ru')
            },
            'customized_approach': {
                'en': req.get_customized_approach_objective('en'),
                'uk': req.get_customized_approach_objective('uk'),
                'ru': req.get_customized_approach_objective('ru')
            },
            'good_practice': {
                'en': req.get_good_practice('en'),
                'uk': req.get_good_practice('uk'),
                'ru': req.get_good_practice('ru')
            }
        }
    except Exception as e:
        logger.error(f"Error formatting requirement data: {str(e)}")
        return {
            'id': req.id,
            'requirement_number': req.requirement_number,
            'category': {},
            'title': {},
            'description': {},
            'testing_procedures': {},
            'customized_approach': {},
            'good_practice': {}
        }


@require_POST
def search_pcidss_with_ai(request):
    try:
        data = json.loads(request.body)
        query = data.get('query')
        current_language = data.get('language', 'en')
        logger.info(f"Received search query: {query}")
        
        if not query:
            return JsonResponse({
                'success': False,
                'error': 'Search query is required'
            })

        # Отримуємо тільки необхідні поля з бази даних
        requirements = PCIDSSRequirement.objects.values(
            'id',
            'requirement_number',
            'title',
            'description'
        )

        # Створюємо скорочений текст вимог
        requirements_text = "\n".join([
            f"({req['requirement_number']}): {(req['title'] or '')[:100]}"
            for req in requirements
        ])

        # Оптимізований промпт
        prompt = f"""Find PCI DSS requirements related to: {query}

        Available requirements:
        {requirements_text}

        Return ONLY requirement numbers in parentheses that are most relevant, followed by a brief explanation.
        Format: (X.Y.Z), (A.B.C)
        Explanation: Brief reason why these requirements are relevant.
        """

        # Отримання налаштувань Claude
        claude_settings = APISettingsClaude.objects.first()
        if not claude_settings:
            return JsonResponse({
                'success': False,
                'error': 'Claude API settings not configured'
            })

        try:
            # Виклик API Claude з обмеженням токенів
            client = anthropic.Anthropic(api_key=claude_settings.api_key)
            response = client.messages.create(
                model=claude_settings.model_name.model_id,
                max_tokens=1000,  # Обмежуємо максимальну кількість токенів
                temperature=0.3,  # Зменшуємо температуру для більш точних відповідей
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Парсинг відповіді
            ai_response = response.content[0].text
            logger.info(f"Received response from Claude: {ai_response}")

            # Витягуємо номери вимог та пояснення
            requirement_numbers = re.findall(r'\((\d+\.\d+(?:\.\d+)?)\)', ai_response)
            explanation = ai_response.split('Explanation:', 1)[1].strip() if 'Explanation:' in ai_response else ai_response

            # Перекладаємо пояснення
            if current_language != 'en' and explanation:
                try:
                    translator = GoogleTranslator(source='en', target=current_language)
                    explanation = translator.translate(explanation)
                except Exception as e:
                    logger.error(f"Translation error: {str(e)}")

            # Знаходимо вимоги за номерами
            found_requirements = PCIDSSRequirement.objects.filter(
                requirement_number__in=requirement_numbers
            ).select_related('category')

            requirements_data = [format_requirement_data(req) for req in found_requirements]

            return JsonResponse({
                'success': True,
                'requirements': requirements_data,
                'explanation': explanation
            })

        except anthropic.RateLimitError:
            error_messages = {
                'en': "Too many requests. Please try again in a minute.",
                'uk': "Забагато запитів. Будь ласка, спробуйте через хвилину.",
                'ru': "Слишком много запросов. Пожалуйста, попробуйте через минуту."
            }
            return JsonResponse({
                'success': False,
                'error': error_messages.get(current_language, error_messages['en'])
            }, status=429)

    except Exception as e:
        logger.error(f"Error in search_pcidss_with_ai: {str(e)}", exc_info=True)
        error_messages = {
            'en': "An error occurred while processing your request.",
            'uk': "Виникла помилка під час обробки вашого запиту.",
            'ru': "Произошла ошибка при обработке вашего запроса."
        }
        return JsonResponse({
            'success': False,
            'error': error_messages.get(current_language, error_messages['en'])
        }, status=500)

def translate_explanation(text, target_language='uk'):
    """Translate explanation text using GoogleTranslator from deep_translator"""
    try:
        if target_language == 'en':
            return text
        
        # Розділяємо текст на частини перед перекладом
        parts = text.split('\n\n')
        if not parts:
            return text
            
        # Перша частина містить номери вимог - не перекладаємо
        requirements_part = parts[0]
        
        # Перекладаємо тільки частину з поясненням
        explanation_part = '\n\n'.join(parts[1:])
        if not explanation_part.strip():
            return text
            
        translator = GoogleTranslator(source='en', target=target_language)
        translated_explanation = translator.translate(explanation_part)
        
        # Об'єднуємо назад
        translated_text = f"{requirements_part}\n\n{translated_explanation}"
        
        logger.info(f"Translation successful: {translated_text[:100]}...")
        return translated_text
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return text  # Повертаємо оригінальний текст у випадку помилки

def translate_iso_explanation(text, target_language='uk'):
    """Translate ISO 27002 explanation text to the target language"""
    if not text or target_language == 'en':
        return text
    
    try:
        translator = GoogleTranslator(source='en', target=target_language)
        translated_text = translator.translate(text)
        logger.info(f"ISO translation successful: {translated_text[:100]}...")
        return translated_text
    except Exception as e:
        logger.error(f"ISO translation error: {str(e)}")
        return text


@require_POST
@ensure_csrf_cookie
def search_pcidss_with_google(request):
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, 
                              status=403)

        data = json.loads(request.body)
        query = data.get('query')
        language = data.get('language', 'en')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Query is required'}, 
                              status=400)

        # Get Google settings and initialize model
        google_settings = APISettingsGoogle.objects.first()
        if not google_settings or not google_settings.model_name:
            return JsonResponse({
                'success': False,
                'error': 'Google AI model not configured'
            }, status=500)

        # Initialize Google AI
        try:
            genai.configure(api_key=google_settings.api_key)
            google_ai = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
        except Exception as e:
            logger.error(f"Error initializing Google AI: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to initialize Google AI'
            }, status=500)

        # Перевіряємо наявність вимог у базі даних
        if not PCIDSSRequirement.objects.exists():
            error_message = "No PCI DSS requirements found in database"
            logger.error(error_message)
            return JsonResponse({
                'success': False,
                'error': error_message,
                'requirements': [],
                'explanation': 'Database is empty or not properly initialized'
            }, status=404)

        # Отримуємо всі доступні вимоги
        available_requirements = list(PCIDSSRequirement.objects.values_list(
            'requirement_number', flat=True
        ))
        
        if not available_requirements:
            error_message = "No valid requirement numbers found in database"
            logger.error(error_message)
            return JsonResponse({
                'success': False,
                'error': error_message,
                'requirements': [],
                'explanation': 'No valid requirements available'
            }, status=404)
        
        # Формуємо контекст
        requirements_context = PCIDSSRequirement.objects.values_list(
            'requirement_number', 'title', 'description'
        )
        
        # Додаємо список доступних вимог у промпт
        available_numbers = ", ".join(sorted(available_requirements))
        
        context = "\n\n".join([
            f"Requirement {req[0]}:\n"
            f"Title: {req[1]}\n"
            f"Description: {req[2]}"
            for req in requirements_context
        ])

        # Визначаємо мову для відповіді
        language_instructions = ""
        response_language = "English"
        explanation_header = "Explanation"
        
        if language == 'uk':
            response_language = "Ukrainian"
            explanation_header = "Пояснення"
            language_instructions = "Write your explanation in Ukrainian language."
        elif language == 'ru':
            response_language = "Russian"
            explanation_header = "Объяснение"
            language_instructions = "Write your explanation in Russian language."

        # Оновлений промпт з списком доступних вимог та інструкціями щодо мови
        prompt = f"""As a PCI DSS expert, identify specific requirements related to: {query}

        Available requirement numbers: {available_numbers}

        Available PCI DSS requirements:
        {context}

        Task:
        1. Find requirements that DIRECTLY relate to {query}
        2. Use ONLY requirements from the available list above
        3. Focus on requirements that mention specific procedures, testing, or controls
        4. Consider both primary requirements and their dependencies

        Response format must be EXACTLY:
        (X.Y.Z), (A.B.C)

        {explanation_header}: For each requirement, explain specifically how it relates to {query}...

        Important:
        - Use only requirements from the available list
        - Include BOTH primary and supporting requirements
        - Explain the direct connection to the query
        - Be specific and technical in explanations
        - {language_instructions} Write your entire response in {response_language} language."""

        try:
            response = google_ai.generate_content(prompt)
            ai_response = response.text
            logger.info(f"AI Response received: {ai_response}")

            # Отримуємо номери вимог
            requirement_numbers = extract_requirement_numbers(ai_response)
            logger.info(f"Extracted requirement numbers: {requirement_numbers}")

            if not requirement_numbers:
                return JsonResponse({
                    'success': True,
                    'requirements': [],
                    'explanation': ai_response,
                    'debug_info': {
                        'error': 'No requirement numbers found in AI response',
                        'raw_text': ai_response
                    }
                })

            # Фільтруємо тільки доступні вимоги
            valid_numbers = [num for num in requirement_numbers 
                           if num in available_requirements]
            
            if not valid_numbers:
                return JsonResponse({
                    'success': True,
                    'requirements': [],
                    'explanation': ai_response,
                    'debug_info': {
                        'error': 'No valid requirements found',
                        'extracted_numbers': requirement_numbers,
                        'available_numbers': available_requirements
                    }
                })

            # Отримуємо вимоги з бази даних
            requirements = PCIDSSRequirement.objects.filter(
                requirement_number__in=valid_numbers
            ).select_related('category')
            
            if not requirements:
                return JsonResponse({
                    'success': True,
                    'requirements': [],
                    'explanation': ai_response,
                    'debug_info': {
                        'error': 'No requirements found in database',
                        'valid_numbers': valid_numbers
                    }
                })
            
            # Форматуємо дані
            requirements_data = [format_requirement_data(req) for req in requirements]

            return JsonResponse({
                'success': True,
                'requirements': requirements_data,
                'explanation': ai_response,
                'debug_info': {
                    'raw_text': ai_response,
                    'target_language': language,
                    'extracted_numbers': requirement_numbers,
                    'valid_numbers': valid_numbers,
                    'found_numbers': [req.requirement_number for req in requirements],
                    'missing_numbers': list(
                        set(requirement_numbers) - set(valid_numbers)
                    ),
                    'requirements_count': len(requirements_data),
                    'available_requirements_count': len(available_requirements)
                }
            })

        except Exception as e:
            logger.error(f"AI processing error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"AI processing error: {str(e)}",
                'requirements': []
            }, status=500)

    except Exception as e:
        logger.error(f"Error in search_pcidss_with_google: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'requirements': []
        }, status=500)


def extract_requirement_numbers(text):
    """Extract requirement numbers from AI response"""
    try:
        logger.info(f"Input text: {text}")
        
        # Спрощений пошук всіх номерів
        pattern = r'\((\d+\.\d+\.\d+)\)'
        all_matches = re.findall(pattern, text)
        logger.info(f"All matches found: {all_matches}")
        
        # Перевіряємо кожен знайдений номер
        valid_numbers = []
        for number in all_matches:
            try:
                # Перевіряємо формат X.Y.Z
                parts = number.split('.')
                if len(parts) == 3 and all(part.isdigit() for part in parts):
                    valid_numbers.append(number)
            except Exception as e:
                logger.error(f"Error validating number {number}: {str(e)}")
                continue
        
        # Видаляємо дублікати та сортуємо
        unique_numbers = list(dict.fromkeys(valid_numbers))
        sorted_numbers = sorted(unique_numbers, 
                              key=lambda x: [int(n) for n in x.split('.')])
        
        logger.info(f"Final valid numbers: {sorted_numbers}")
        
        # Додаткова перевірка результатів
        if len(all_matches) != len(sorted_numbers):
            logger.warning(
                f"Some numbers were filtered: Original {all_matches} -> Final {sorted_numbers}"
            )
        
        if not sorted_numbers:
            logger.error(f"No valid numbers found in text: {text}")
        
        return sorted_numbers
        
    except Exception as e:
        logger.error(f"Error in extract_requirement_numbers: {str(e)}", exc_info=True)
        logger.error(f"Problematic text: {text}")
        return []


def translate_ai_response(text, target_language):
    """Translate AI response to target language"""
    try:
        # Розділяємо текст на частини
        requirements = ""
        explanation = ""
        
        # Спробуємо різні варіанти розділення тексту
        if 'Explanation:' in text:
            parts = text.split('Explanation:', 1)
            requirements = parts[0].strip()
            explanation = parts[1].strip() if len(parts) > 1 else ""
        elif '\n\n' in text:
            # Якщо немає явного розділення, спробуємо розділити за подвійним переносом рядка
            # Перший блок - вимоги, решта - пояснення
            parts = text.split('\n\n', 1)
            requirements = parts[0].strip()
            explanation = parts[1].strip() if len(parts) > 1 else ""
        else:
            # Якщо не можемо розділити, вважаємо весь текст поясненням
            requirements = ""
            explanation = text.strip()
        
        logger.info(f"Split text into requirements: '{requirements[:50]}...' and explanation: '{explanation[:50]}...'")

        # Переклад заголовків
        headers = {
            'uk': {
                'found_requirements': 'Знайдені вимоги',
                'explanation': 'Пояснення'
            },
            'ru': {
                'found_requirements': 'Найденные требования',
                'explanation': 'Объяснение'
            }
        }

        if target_language in ['uk', 'ru']:
            try:
                translator = GoogleTranslator(source='en', target=target_language)
                # Зберігаємо номери вимог
                req_numbers = re.findall(r'\([\d\.]+\)', requirements)
                
                # Перекладаємо пояснення
                translated_explanation = translator.translate(explanation.strip()) if explanation else ""
                
                # Формуємо перекладену відповідь
                if requirements and explanation:
                    header = headers[target_language]['explanation']
                    translated_text = f"{', '.join(req_numbers)}\n\n{header}: {translated_explanation}"
                elif requirements:
                    translated_text = ', '.join(req_numbers)
                else:
                    translated_text = translated_explanation
                
                logger.info(f"Translated response to {target_language}")
                return translated_text
            except Exception as e:
                logger.error(f"Translation error: {str(e)}")
                return text
            
        return text

    except Exception as e:
        logger.error(f"Error in translate_ai_response: {str(e)}")
        return text


@require_POST
@ensure_csrf_cookie
def search_pcidss_with_claude(request):
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=403)

        claude_settings = APISettingsClaude.objects.first()
        if not claude_settings or not claude_settings.model_name:
            return JsonResponse({
                'success': False,
                'error': 'Claude AI model not configured'
            }, status=500)

        data = json.loads(request.body)
        query = data.get('query')
        language = data.get('language', 'en')
        
        if not query:
            return JsonResponse({
                'success': False,
                'error': 'Query is required'
            }, status=400)

        # Get all available requirements for context
        requirements_context = PCIDSSRequirement.objects.values_list(
            'requirement_number', 'title'
        )
        context = "\n".join([f"({req[0]}): {req[1] or ''}" for req in requirements_context])

        # Determine response language
        language_instructions = ""
        response_language = "English"
        explanation_header = "Explanation"
        
        if language == 'uk':
            response_language = "Ukrainian"
            explanation_header = "Пояснення"
            language_instructions = "Write your explanation in Ukrainian language."
        elif language == 'ru':
            response_language = "Russian"
            explanation_header = "Объяснение"
            language_instructions = "Write your explanation in Russian language."

        # Create prompt with language instructions
        prompt = f"""Find PCI DSS requirements related to: {query}

        Available requirements:
        {context}

        Return ONLY requirement numbers in parentheses that are most relevant, followed by a brief explanation.
        Format: (X.Y.Z), (A.B.C)
        {explanation_header}: Brief reason why these requirements are relevant.
        
        IMPORTANT: {language_instructions} Write your entire response in {response_language} language."""

        # Generate response from Claude
        try:
            client = Anthropic(api_key=claude_settings.api_key)
            message = client.messages.create(
                model=claude_settings.model_name.model_id,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            ai_response = message.content[0].text

            # Extract requirement numbers and get requirements
            requirement_numbers = extract_requirement_numbers(ai_response)
            logger.info(f"Found requirement numbers: {requirement_numbers}")

            if not requirement_numbers:
                logger.warning("No requirement numbers found in AI response")
                return JsonResponse({
                    'success': True,
                    'requirements': [],
                    'explanation': ai_response
                })

            requirements = PCIDSSRequirement.objects.filter(
                requirement_number__in=requirement_numbers
            ).select_related('category')

            # Format requirements data
            requirements_data = [format_requirement_data(req) for req in requirements]

            return JsonResponse({
                'success': True,
                'requirements': requirements_data,
                'explanation': ai_response
            })

        except Exception as e:
            logger.error(f"AI processing error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"AI processing error: {str(e)}"
            }, status=500)

    except Exception as e:
        logger.error(f"Error in search_pcidss_with_claude: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
@ensure_csrf_cookie
def search_pcidss_with_deepseek(request):
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
        language = data.get('language', 'en')
        logger.info(f"Received search query for DeepSeek: {query}")
        
        if not query:
            return JsonResponse({
                'success': False,
                'error': 'Search query is required'
            })

        # Get DeepSeek settings
        deepseek_settings = APISettingsDeepSeek.objects.first()
        if not deepseek_settings or not deepseek_settings.model_name:
            return JsonResponse({
                'success': False,
                'error': 'DeepSeek API settings not configured'
            })

        # Prepare data for request
        requirements = PCIDSSRequirement.objects.values(
            'id',
            'requirement_number',
            'title',
            'description'
        )

        requirements_text = "\n".join([
            f"({req['requirement_number']}): {(req['title'] or '')[:100]}"
            for req in requirements
        ])

        # Determine response language
        language_instructions = ""
        response_language = "English"
        explanation_header = "Explanation"
        
        if language == 'uk':
            response_language = "Ukrainian"
            explanation_header = "Пояснення"
            language_instructions = "Write your explanation in Ukrainian language."
        elif language == 'ru':
            response_language = "Russian"
            explanation_header = "Объяснение"
            language_instructions = "Write your explanation in Russian language."

        # Create DeepSeek client
        client = openai.OpenAI(
            api_key=deepseek_settings.api_key,
            base_url="https://api.deepseek.com"
        )

        # Send request with language instructions
        response = client.chat.completions.create(
            model=deepseek_settings.model_name.model_id,
            messages=[
                {"role": "system", "content": f"You are a PCI DSS expert. Analyze the query and find relevant requirements. {language_instructions}"},
                {"role": "user", "content": f"""Find PCI DSS requirements related to: {query}

                Available requirements:
                {requirements_text}

                Return ONLY requirement numbers in parentheses that are most relevant, followed by a brief explanation.
                Format: (X.Y.Z), (A.B.C)
                {explanation_header}: Brief reason why these requirements are relevant.
                
                IMPORTANT: Write your explanation in {response_language} language."""}
            ],
            temperature=deepseek_settings.temperature,
            max_tokens=deepseek_settings.max_tokens,
            top_p=deepseek_settings.top_p,
            frequency_penalty=deepseek_settings.frequency_penalty,
            presence_penalty=deepseek_settings.presence_penalty
        )

        # Process response
        ai_response = response.choices[0].message.content
        
        # Parse response (no translation needed as response should already be in the correct language)
        requirement_numbers = extract_requirement_numbers(ai_response)
        logger.info(f"Found requirement numbers: {requirement_numbers}")

        if not requirement_numbers:
            logger.warning("No requirement numbers found in DeepSeek AI response")
            return JsonResponse({
                'success': True,
                'requirements': [],
                'explanation': ai_response
            })

        # Find requirements by numbers
        found_requirements = PCIDSSRequirement.objects.filter(
            requirement_number__in=requirement_numbers
        ).select_related('category')

        requirements_data = [format_requirement_data(req) for req in found_requirements]

        return JsonResponse({
            'success': True,
            'requirements': requirements_data,
            'explanation': ai_response
        })

    except Exception as e:
        logger.error(f"Error in search_pcidss_with_deepseek: {str(e)}", exc_info=True)
        error_messages = {
            'en': "An error occurred while processing your request.",
            'uk': "Виникла помилка під час обробки вашого запиту.",
            'ru': "Произошла ошибка при обработке вашего запроса."
        }
        return JsonResponse({
            'success': False,
            'error': error_messages.get(language, error_messages['en'])
        }, status=500)


# ISO 27002 AI search functions
def format_control_data(control):
    """Format ISO 27002 control data for AI processing"""
    try:
        control_data = {
            'id': control.id,
            'control_number': control.control_number,
            'theme': control.theme.name if control.theme else None,
            'title': {
                'en': control.get_title('en') or '',
                'uk': control.get_title('uk') or '',
                'ru': control.get_title('ru') or ''
            },
            'control_description': {
                'en': control.get_control_description('en') or '',
                'uk': control.get_control_description('uk') or '',
                'ru': control.get_control_description('ru') or ''
            },
            'purpose': {
                'en': control.get_purpose('en') or '',
                'uk': control.get_purpose('uk') or '',
                'ru': control.get_purpose('ru') or ''
            },
            'guidance': {
                'en': control.get_guidance('en') or '',
                'uk': control.get_guidance('uk') or '',
                'ru': control.get_guidance('ru') or ''
            },
            'other_information': {
                'en': control.get_other_information('en') or '',
                'uk': control.get_other_information('uk') or '',
                'ru': control.get_other_information('ru') or ''
            },
            'control_type': control.control_type or '',
            'security_domain': control.security_domain or '',
            'information_security_properties': control.information_security_properties or [],
            'cybersecurity_concepts': control.cybersecurity_concepts or []
        }
        return control_data
    except Exception as e:
        logger.error(f"Error formatting control data for control ID {control.id}: {str(e)}")
        # Return a minimal valid control data object
        return {
            'id': control.id,
            'control_number': getattr(control, 'control_number', 'Unknown'),
            'title': {'en': control.get_title('en') or 'Unknown Control'},
            'control_description': {'en': control.get_control_description('en') or ''}
        }

@csrf_exempt
@require_POST
def search_iso27002_with_google(request):
    """Search ISO 27002 controls using Google AI"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
        language = data.get('language', 'en')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Query is required'})
        
        # Get Google settings and initialize model
        google_settings = APISettingsGoogle.objects.first()
        if not google_settings or not google_settings.model_name:
            return JsonResponse({
                'success': False,
                'error': 'Google AI model not configured'
            }, status=500)

        # Initialize Google AI
        try:
            genai.configure(api_key=google_settings.api_key)
            google_ai = genai.GenerativeModel(google_settings.model_name.model_id)  # Use model_id instead of model_name
        except Exception as e:
            logger.error(f"Error initializing Google AI: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to initialize Google AI'
            }, status=500)

        # Get all ISO 27002 controls
        controls = ISO27002Control.objects.all()
        
        if not controls.exists():
            error_message = "No ISO 27002 controls found in database"
            logger.error(error_message)
            return JsonResponse({
                'success': False,
                'error': error_message,
                'controls': [],
                'explanation': 'Database is empty or not properly initialized'
            }, status=404)
        
        # Limit the number of controls to prevent token limit issues
        # First, try to find controls that might be relevant to the query
        query_terms = query.lower().split()
        filtered_controls = []
        
        for control in controls:
            # Check if any query term appears in the title or description
            if any(term in (control.get_title('en') or control.title or '').lower() for term in query_terms) or \
               any(term in (control.get_control_description('en') or control.control_description or '').lower() for term in query_terms):
                filtered_controls.append(control)
        
        # If we found relevant controls, use them; otherwise, take a sample
        if filtered_controls:
            controls_to_use = filtered_controls[:5]  # Limit to 5 relevant controls
        else:
            controls_to_use = list(controls)[:5]  # Just take the first 5 controls
            
        # Create simplified control data to reduce token count
        simplified_controls = []
        for control in controls_to_use:
            simplified_controls.append({
                'id': control.id,
                'control_number': control.control_number,
                'title': control.get_title('en') or control.title,
                'control_description': (control.get_control_description('en') or control.control_description or '')[:500],
                'theme': control.theme.name if control.theme else None,
                'control_type': control.control_type
            })
        
        # Prepare prompt for Google AI
        prompt = f"""
        You are an expert in ISO 27002 information security controls. I will provide you with a question about ISO 27002 controls, and you need to:
        1. Identify the most relevant ISO 27002 controls that address the question
        2. Provide a detailed explanation of how these controls relate to the question
        3. Format your response in a structured way

        Here is the question: {query}

        Here is a sample of ISO 27002 controls in JSON format:
        {json.dumps(simplified_controls)}

        Please respond with:
        1. A list of the most relevant control numbers and titles
        2. A detailed explanation of how these controls address the question
        3. Any additional recommendations or best practices
        
        Format your response as JSON with the following structure:
        {{
            "controls": [
                {{
                    "control_number": "control number",
                    "title": "control title",
                    "control_description": "description of the control",
                    "theme": "control theme",
                    "control_type": "control type",
                    "guidance": "guidance for implementing the control",
                    "purpose": "purpose of the control"
                }}
            ],
            "explanation": "detailed explanation of how these controls address the question"
        }}
        """
        
        # Generate response from Google AI
        response = google_ai.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no JSON block found, try to extract JSON directly
                json_match = re.search(r'({.*})', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    raise ValueError("No JSON found in response")
            
            result = json.loads(json_str)
            
            # Ensure the result has the expected structure
            if 'controls' not in result or 'explanation' not in result:
                raise ValueError("Response missing required fields")
            
            # Ensure each control has the required fields
            for control in result.get('controls', []):
                # Add language structure to text fields if not present
                for field in ['title', 'control_description', 'guidance', 'purpose']:
                    if field in control and isinstance(control[field], str):
                        control[field] = {'en': control[field]}
            
            # Translate explanation if needed
            if language != 'en':
                result['explanation'] = translate_iso_explanation(result['explanation'], language)
            
            return JsonResponse({'success': True, **result})
        except Exception as e:
            logger.error(f"Error parsing Google AI response: {str(e)}", exc_info=True)
            logger.error(f"Response text: {response_text}")
            return JsonResponse({'success': False, 'error': f'Error parsing AI response: {str(e)}'})
    
    except Exception as e:
        logger.error(f"Error in search_iso27002_with_google: {str(e)}", exc_info=True)
        error_messages = {
            'en': "An error occurred while processing your request.",
            'uk': "Виникла помилка під час обробки вашого запиту.",
            'ru': "Произошла ошибка при обработке вашего запроса."
        }
        return JsonResponse({
            'success': False,
            'error': error_messages.get(language, error_messages['en'])
        }, status=500)

@csrf_exempt
@require_POST
def search_iso27002_with_claude(request):
    """Search ISO 27002 controls using Claude AI"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
        language = data.get('language', 'en')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Query is required'})
        
        # Get Claude settings
        claude_settings = APISettingsClaude.objects.first()
        if not claude_settings or not claude_settings.model_name:
            return JsonResponse({
                'success': False,
                'error': 'Claude AI settings not configured'
            }, status=500)

        # Initialize Claude AI with proper model_id
        try:
            claude_ai = Anthropic(api_key=claude_settings.api_key)
            model_id = claude_settings.model_name.model_id  # Get the model_id from ModelChoice
        except Exception as e:
            logger.error(f"Error initializing Claude AI: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to initialize Claude AI'
            }, status=500)

        # Get all ISO 27002 controls
        controls = ISO27002Control.objects.all()
        
        if not controls.exists():
            error_message = "No ISO 27002 controls found in database"
            logger.error(error_message)
            return JsonResponse({
                'success': False,
                'error': error_message,
                'controls': [],
                'explanation': 'Database is empty or not properly initialized'
            }, status=404)
        
        # Limit the number of controls to prevent token limit issues
        # First, try to find controls that might be relevant to the query
        query_terms = query.lower().split()
        filtered_controls = []
        
        for control in controls:
            # Check if any query term appears in the title or description
            if any(term in (control.get_title('en') or control.title or '').lower() for term in query_terms) or \
               any(term in (control.get_control_description('en') or control.control_description or '').lower() for term in query_terms):
                filtered_controls.append(control)
        
        # If we found relevant controls, use them; otherwise, take a sample
        if filtered_controls:
            controls_to_use = filtered_controls[:5]  # Limit to 5 relevant controls
        else:
            controls_to_use = list(controls)[:5]  # Just take the first 5 controls
            
        # Create simplified control data to reduce token count
        simplified_controls = []
        for control in controls_to_use:
            simplified_controls.append({
                'id': control.id,
                'control_number': control.control_number,
                'title': control.get_title('en') or control.title,
                'control_description': (control.get_control_description('en') or control.control_description or '')[:500],
                'theme': control.theme.name if control.theme else None,
                'control_type': control.control_type
            })

        # Prepare prompt for Claude AI
        prompt = f"""
        You are an expert in ISO 27002 information security controls. I will provide you with a question about ISO 27002 controls, and you need to:
        1. Identify the most relevant ISO 27002 controls that address the question
        2. Provide a detailed explanation of how these controls relate to the question
        3. Format your response in a structured way

        Here is the question: {query}

        Here is a sample of ISO 27002 controls in JSON format:
        {json.dumps(simplified_controls)}

        Please respond with:
        1. A list of the most relevant control numbers and titles
        2. A detailed explanation of how these controls address the question
        3. Any additional recommendations or best practices
        
        Format your response as JSON with the following structure:
        {{
            "controls": [
                {{
                    "control_number": "control number",
                    "title": "control title",
                    "control_description": "description of the control",
                    "theme": "control theme",
                    "control_type": "control type",
                    "guidance": "guidance for implementing the control",
                    "purpose": "purpose of the control"
                }}
            ],
            "explanation": "detailed explanation of how these controls address the question"
        }}
        """
        
        # Generate response from Claude AI with proper model_id
        response = claude_ai.messages.create(
            model=model_id,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', response.content[0].text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no JSON block found, try to extract JSON directly
                json_match = re.search(r'({.*})', response.content[0].text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    raise ValueError("No JSON found in response")
            
            result = json.loads(json_str)
            
            # Ensure the result has the expected structure
            if 'controls' not in result or 'explanation' not in result:
                raise ValueError("Response missing required fields")
            
            # Ensure each control has the required fields
            for control in result.get('controls', []):
                # Add language structure to text fields if not present
                for field in ['title', 'control_description', 'guidance', 'purpose']:
                    if field in control and isinstance(control[field], str):
                        control[field] = {'en': control[field]}
            
            # Translate explanation if needed
            if language != 'en':
                result['explanation'] = translate_iso_explanation(result['explanation'], language)
            
            return JsonResponse({'success': True, **result})
        except Exception as e:
            logger.error(f"Error parsing Claude AI response: {str(e)}", exc_info=True)
            logger.error(f"Response text: {response.content[0].text}")
            return JsonResponse({'success': False, 'error': f'Error parsing AI response: {str(e)}'})
    
    except Exception as e:
        logger.error(f"Error in search_iso27002_with_claude: {str(e)}", exc_info=True)
        error_messages = {
            'en': "An error occurred while processing your request.",
            'uk': "Виникла помилка під час обробки вашого запиту.",
            'ru': "Произошла ошибка при обработке вашего запроса."
        }
        return JsonResponse({
            'success': False,
            'error': error_messages.get(language, error_messages['en'])
        }, status=500)

@csrf_exempt
@require_POST
def search_iso27002_with_deepseek(request):
    """Search ISO 27002 controls using DeepSeek AI"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
        language = data.get('language', 'en')
        
        if not query:
            return JsonResponse({'success': False, 'error': 'Query is required'})
        
        # Get DeepSeek settings
        deepseek_settings = APISettingsDeepSeek.objects.first()
        if not deepseek_settings or not deepseek_settings.model_name:
            return JsonResponse({
                'success': False,
                'error': 'DeepSeek API settings not configured'
            }, status=500)

        # Get the model_id from ModelChoice
        try:
            model_id = deepseek_settings.model_name.model_id
        except Exception as e:
            logger.error(f"Error getting DeepSeek model ID: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid DeepSeek model configuration'
            }, status=500)

        # Get all ISO 27002 controls
        controls = ISO27002Control.objects.all()
        
        if not controls.exists():
            error_message = "No ISO 27002 controls found in database"
            logger.error(error_message)
            return JsonResponse({
                'success': False,
                'error': error_message,
                'controls': [],
                'explanation': 'Database is empty or not properly initialized'
            }, status=404)
        
        # Limit the number of controls to prevent token limit issues
        # First, try to find controls that might be relevant to the query
        query_terms = query.lower().split()
        filtered_controls = []
        
        for control in controls:
            # Check if any query term appears in the title or description
            if any(term in (control.get_title('en') or control.title or '').lower() for term in query_terms) or \
               any(term in (control.get_control_description('en') or control.control_description or '').lower() for term in query_terms):
                filtered_controls.append(control)
        
        # If we found relevant controls, use them; otherwise, take a sample
        if filtered_controls:
            controls_to_use = filtered_controls[:3]  # Limit to 3 relevant controls for DeepSeek
        else:
            controls_to_use = list(controls)[:3]  # Just take the first 3 controls
        
        # Create simplified control data to reduce token count
        simplified_controls = []
        for control in controls_to_use:
            simplified_controls.append({
                'id': control.id,
                'control_number': control.control_number,
                'title': control.get_title('en') or control.title,
                'control_description': (control.get_control_description('en') or control.control_description or '')[:500],
                'theme': control.theme.name if control.theme else None,
                'control_type': control.control_type
            })

        # Prepare prompt for DeepSeek AI
        prompt = f"""
        You are an expert in ISO 27002 information security controls. I will provide you with a question about ISO 27002 controls, and you need to:
        1. Identify the most relevant ISO 27002 controls that address the question
        2. Provide a detailed explanation of how these controls relate to the question
        3. Format your response in a structured way

        Here is the question: {query}

        Here is a sample of ISO 27002 controls in JSON format:
        {json.dumps(simplified_controls)}

        Please respond with:
        1. A list of the most relevant control numbers and titles
        2. A detailed explanation of how these controls address the question
        3. Any additional recommendations or best practices
        
        Format your response as JSON with the following structure:
        {{
            "controls": [
                {{
                    "control_number": "control number",
                    "title": "control title",
                    "control_description": "description of the control",
                    "theme": "control theme",
                    "control_type": "control type",
                    "guidance": "guidance for implementing the control",
                    "purpose": "purpose of the control"
                }}
            ],
            "explanation": "detailed explanation of how these controls address the question"
        }}
        """
        
        # Create DeepSeek client
        client = openai.OpenAI(
            api_key=deepseek_settings.api_key,
            base_url="https://api.deepseek.com/v1"
        )

        # Send request with proper model_id
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "You are an expert in ISO 27002 information security controls."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', response.choices[0].message.content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no JSON block found, try to extract JSON directly
                json_match = re.search(r'({.*})', response.choices[0].message.content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    raise ValueError("No JSON found in response")
            
            result = json.loads(json_str)
            
            # Ensure the result has the expected structure
            if 'controls' not in result or 'explanation' not in result:
                raise ValueError("Response missing required fields")
            
            # Ensure each control has the required fields
            for control in result.get('controls', []):
                # Add language structure to text fields if not present
                for field in ['title', 'control_description', 'guidance', 'purpose']:
                    if field in control and isinstance(control[field], str):
                        control[field] = {'en': control[field]}
            
            # Translate explanation if needed
            if language != 'en':
                result['explanation'] = translate_iso_explanation(result['explanation'], language)
            
            return JsonResponse({'success': True, **result})
        except Exception as e:
            logger.error(f"Error parsing DeepSeek AI response: {str(e)}", exc_info=True)
            logger.error(f"Response text: {response.choices[0].message.content}")
            return JsonResponse({'success': False, 'error': f'Error parsing AI response: {str(e)}'})
    
    except Exception as e:
        logger.error(f"Error in search_iso27002_with_deepseek: {str(e)}", exc_info=True)
        error_messages = {
            'en': "An error occurred while processing your request.",
            'uk': "Виникла помилка під час обробки вашого запиту.",
            'ru': "Произошла ошибка при обработке вашего запроса."
        }
        return JsonResponse({
            'success': False,
            'error': error_messages.get(language, error_messages['en'])
        }, status=500)

@login_required
def pcidss_documents(request):
    """View for listing and managing PCI DSS documents"""
    # Check if user has permission to access PCI DSS
    has_access = check_pcidss_access(request.user)
    if not has_access:
        return render(request, 'access_denied.html')
    
    # Check if user has edit permission
    can_edit = check_pcidss_edit_access(request.user)
    
    documents = PCIDSSDocument.objects.all().order_by('-uploaded_at')
    context = {
        'documents': documents,
        'can_edit': can_edit
    }
    return render(request, 'app_std/pcidss_documents.html', context)

@login_required
@require_POST
@csrf_exempt  # Temporary exemption for testing
def upload_pcidss_document(request):
    """Handle document upload"""
    # Check if user has edit permission
    can_edit = check_pcidss_edit_access(request.user)
    if not can_edit:
        return JsonResponse({'success': False, 'error': _('Permission denied')}, status=403)
    
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'error': _('No file was uploaded')})
    
    file = request.FILES['file']
    if not file.name.endswith('.pdf'):
        return JsonResponse({'success': False, 'error': _('Only PDF files are allowed')})
    
    title = request.POST.get('title', file.name)
    description = request.POST.get('description', '')
    
    try:
        document = PCIDSSDocument.objects.create(
            title=title,
            description=description,
            file=file
        )
        return JsonResponse({
            'success': True, 
            'document': {
                'id': document.id,
                'title': document.title,
                'description': document.description,
                'filename': document.filename(),
                'uploaded_at': document.uploaded_at.strftime('%Y-%m-%d %H:%M')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def view_pcidss_document(request, document_id):
    """View a specific document"""
    # Check if user has permission to access PCI DSS
    has_access = check_pcidss_access(request.user)
    if not has_access:
        return render(request, 'access_denied.html')
    
    try:
        document = PCIDSSDocument.objects.get(id=document_id)
        file_path = document.file.path
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        
        # Allow embedding in iframes from the same origin
        response['X-Frame-Options'] = 'SAMEORIGIN'
        
        return response
    except PCIDSSDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Document not found')}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
@csrf_exempt  # Temporary exemption for testing
def delete_pcidss_document(request, document_id):
    """Delete a document"""
    # Check if user has edit permission
    can_edit = check_pcidss_edit_access(request.user)
    if not can_edit:
        return JsonResponse({'success': False, 'error': _('Permission denied')}, status=403)
    
    try:
        document = PCIDSSDocument.objects.get(id=document_id)
        file_path = document.file.path
        
        # Delete the document from database
        document.delete()
        
        # Delete the file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return JsonResponse({'success': True})
    except PCIDSSDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Document not found')}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

