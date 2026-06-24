#  SecBoard\SecBoard\app_ai\ai_utils.py
from .models import APISettingsGoogle, APISettingsOllama, APISettingsClaude, APISettingsGroq, APISettingsDeepSeek
import openai
import google.generativeai as genai
from groq import Groq
from ollama import Client
from groq import Groq
from openai import AuthenticationError, APIError
import anthropic
from anthropic import AuthenticationError, APIError
import google.generativeai as genai






def get_ai_response(ai_model, prompt, conversation_history, file_content=''):
    if ai_model == 'ollama':
        return get_ollama_response(prompt, conversation_history, file_content)
    elif ai_model == 'google':
        return get_google_response(prompt, conversation_history, file_content)
    elif ai_model == 'claude':
        return get_claude_response(prompt, conversation_history)
    elif ai_model == 'groq':
        return get_groq_response(prompt, conversation_history)
    elif ai_model == 'deepseek':
        return get_deepseek_response(prompt, conversation_history)
    else:
        return "Unknown AI model selected."


def get_ollama_response(prompt, conversation_history, system_message="You are an AI assistant in an email conversation."):
    settings = APISettingsOllama.objects.first()
    if not settings:
        return "Ollama API settings not found.", None

    client = Client(host=settings.api_url)
    messages = [{"role": "system", "content": system_message}]
    for msg in conversation_history:
        messages.append({"role": msg['role'], "content": msg['content']})
    messages.append({"role": "user", "content": prompt})

    try:
        model_name = settings.model_name.model_id if settings.model_name else 'llama2'
        response = client.chat(
            model=model_name,
            messages=messages
        )
        
        # Extract usage information for Ollama (may not always be available)
        usage_info = None
        if hasattr(response, 'eval_count') and hasattr(response, 'prompt_eval_count'):
            usage_info = {
                'input_tokens': getattr(response, 'prompt_eval_count', None),
                'output_tokens': getattr(response, 'eval_count', None),
                'total_tokens': None
            }
            if usage_info['input_tokens'] is not None and usage_info['output_tokens'] is not None:
                usage_info['total_tokens'] = usage_info['input_tokens'] + usage_info['output_tokens']
        
        return response.message.content, usage_info
    except Exception as e:
        return f"Error occurred while communicating with Ollama: {str(e)}", None


def get_google_response(prompt, conversation_history, system_message=""):
    settings = APISettingsGoogle.objects.first()
    if not settings:
        return "Google API settings not found.", None

    try:
        genai.configure(api_key=settings.api_key)
        model_name = settings.model_name.model_id if settings.model_name else 'gemini-pro'
        
        # Додати системний промпт на початку, якщо він переданий
        full_prompt = prompt
        if system_message:
            full_prompt = f"{system_message}\n\n{prompt}"

        model = genai.GenerativeModel(model_name)

        chat = model.start_chat(history=[])

        # Відправляємо всю історію розмови як одне повідомлення
        full_history = "\n".join(
            [f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}" for msg in conversation_history])

        full_history += f"\nUser: {full_prompt}"

        response = chat.send_message(full_history)
        
        # Extract usage information for Google (may not always be available)
        usage_info = None
        if hasattr(response, 'usage_metadata'):
            usage_metadata = response.usage_metadata
            usage_info = {
                'input_tokens': getattr(usage_metadata, 'prompt_token_count', None),
                'output_tokens': getattr(usage_metadata, 'candidates_token_count', None),
                'total_tokens': None
            }
            if usage_info['input_tokens'] is not None and usage_info['output_tokens'] is not None:
                usage_info['total_tokens'] = usage_info['input_tokens'] + usage_info['output_tokens']
        
        return response.text, usage_info
    except Exception as e:
        return f"An error occurred while communicating with Google AI Studio: {str(e)}", None


def get_groq_response(prompt, conversation_history, system_message="You are an AI assistant in an email conversation."):
    settings = APISettingsGroq.objects.first()
    if not settings:
        return "Groq API settings not found.", None

    client = Groq(api_key=settings.api_key)

    messages = [{"role": "system", "content": system_message}]
    for msg in conversation_history:
        messages.append({"role": msg['role'], "content": msg['content']})
    messages.append({"role": "user", "content": prompt})

    try:
        model_name = settings.model_name.model_id if settings.model_name else 'mixtral-8x7b-32768'
        response = client.chat.completions.create(
            messages=messages,
            model=model_name,
        )
        
        # Extract usage information
        usage_info = None
        if hasattr(response, 'usage') and response.usage:
            usage_info = {
                'input_tokens': getattr(response.usage, 'prompt_tokens', None),
                'output_tokens': getattr(response.usage, 'completion_tokens', None),
                'total_tokens': getattr(response.usage, 'total_tokens', None)
            }
        
        return response.choices[0].message.content, usage_info
    except Exception as e:
        error_message = str(e)
        if "model_not_found" in error_message:
            return f"Error: The specified model '{model_name}' was not found. Please check your Groq API settings.", None
        elif "invalid_request_error" in error_message:
            return f"Error: Invalid request to Groq API. Details: {error_message}", None
        else:
            return f"An error occurred while communicating with Groq API: {error_message}", None


def get_claude_response(prompt, conversation_history, system_prompt=None):
    # Retrieve Claude API settings from the database
    settings = APISettingsClaude.objects.first()
    if not settings:
        return "Claude API settings not found.", None

    try:
        # Initialize the Claude API client with the provided API key
        client = anthropic.Anthropic(api_key=settings.api_key)

        # Use provided system prompt or default
        if system_prompt is None:
            system_prompt = "You are Claude, an AI assistant created by Anthropic to be helpful, harmless, and honest."

        messages = []
        for msg in conversation_history:
            if msg['role'] not in ['user', 'assistant']:
                continue  # Skip messages with invalid roles
            messages.append({"role": msg['role'], "content": msg['content']})

        # Ensure the last message is from 'user' before adding the new prompt
        if messages and messages[-1]['role'] == 'user':
            messages[-1]['content'] += f"\n\n{prompt}"
        else:
            messages.append({"role": "user", "content": prompt})

        # Increase max_tokens to allow for larger responses
        max_tokens = settings.max_tokens + 500  # Increase by 500 or set a fixed large value
        if max_tokens > 4096:  # Assuming 4096 is the maximum allowed by the API
            max_tokens = 4096

        # Create a message to send to the Claude API
        model_name = settings.model_name.model_id if settings.model_name else 'claude-3-5-sonnet-20241022'
        response = client.messages.create(
            model=model_name,
            messages=messages,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=settings.temperature
        )

        # Extract usage information
        usage_info = None
        if hasattr(response, 'usage') and response.usage:
            usage_info = {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens
            }

        # Return the AI response text and usage info
        return response.content[0].text, usage_info

    except anthropic.APIError as e:
        # Handle specific API errors
        return f"Error occurred while communicating with Claude API: {str(e)}", None
    except Exception as e:
        # Handle general exceptions
        return f"An unexpected error occurred: {str(e)}", None


def get_deepseek_response(prompt, conversation_history, system_message="You are an AI assistant in an email conversation."):
    # Retrieve DeepSeek API settings from the database
    settings = APISettingsDeepSeek.objects.first()
    if not settings:
        return "DeepSeek API settings not found.", None

    try:
        # Initialize the DeepSeek API client (uses OpenAI-compatible API)
        from openai import OpenAI
        client = OpenAI(api_key=settings.api_key, base_url="https://api.deepseek.com/v1")

        messages = [{"role": "system", "content": system_message}]
        for msg in conversation_history:
            if msg['role'] not in ['user', 'assistant']:
                continue  # Skip messages with invalid roles
            messages.append({"role": msg['role'], "content": msg['content']})

        # Ensure the last message is from 'user' before adding the new prompt
        if messages and messages[-1]['role'] == 'user':
            messages[-1]['content'] += f"\n\n{prompt}"
        else:
            messages.append({"role": "user", "content": prompt})

        # Create a message to send to the DeepSeek API
        model_name = settings.model_name.model_id if settings.model_name else 'deepseek-chat'
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature
        )

        # Extract usage information
        usage_info = None
        if hasattr(response, 'usage') and response.usage:
            usage_info = {
                'input_tokens': getattr(response.usage, 'prompt_tokens', None),
                'output_tokens': getattr(response.usage, 'completion_tokens', None),
                'total_tokens': getattr(response.usage, 'total_tokens', None)
            }

        # Return the AI response text and usage info
        return response.choices[0].message.content, usage_info

    except Exception as e:
        # Handle general exceptions
        return f"An error occurred while communicating with DeepSeek API: {str(e)}", None


def get_claude_api_key():
    """Anthropic API key from Admin › App_Ai › API Settings Claude."""
    settings = APISettingsClaude.objects.first()
    if not settings or not settings.api_key:
        return ''
    return settings.api_key
