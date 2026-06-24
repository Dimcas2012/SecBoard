#  SecBoard\SecBoard\app_ai\models.py
from django.db import models
from django.core.exceptions import ValidationError
import anthropic
import openai
from openai import OpenAI
from encrypted_model_fields.fields import EncryptedCharField

class ModelChoice(models.Model):
    provider = models.CharField(max_length=50)  # e.g., 'claude', 'groq', 'deepseek'
    model_id = models.CharField(max_length=100)  # e.g., 'claude-3-opus-20240229'
    model_name = models.CharField(max_length=100)  # e.g., 'Claude 3 Opus $15'
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.provider} - {self.model_name}"

    class Meta:
        verbose_name_plural = "Model Choices"
        unique_together = ('provider', 'model_id')

class APISettingsGoogle(models.Model):
    api_key = EncryptedCharField(max_length=255)
    model_name = models.ForeignKey(ModelChoice, on_delete=models.SET_NULL, null=True, limit_choices_to={'provider': 'google', 'is_active': True})
    uploaded_file = models.FileField(upload_to='uploaded_files/', null=True, blank=True)

    def __str__(self):
        return f"API Settings Google - {self.model_name.model_name if self.model_name else 'No model selected'}"

    class Meta:
        verbose_name_plural = "API Settings Google"

class APISettingsOllama(models.Model):
    api_url = models.URLField()
    model_name = models.ForeignKey(ModelChoice, on_delete=models.SET_NULL, null=True, limit_choices_to={'provider': 'ollama', 'is_active': True})
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=100)
    top_p = models.FloatField(default=1.0)
    frequency_penalty = models.FloatField(default=0.0)
    presence_penalty = models.FloatField(default=0.0)
    
    def __str__(self):
        return f"API Settings Ollama - {self.model_name.model_name if self.model_name else 'No model selected'}"

    class Meta:
        verbose_name_plural = "API Settings Ollama"

def validate_claude_api_key(value):
    client = anthropic.Anthropic(api_key=value)
    try:
        # Спроба зробити тестовий запит
        client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello"}]
        )
    except Exception as e:
        raise ValidationError(f"Invalid API key: {str(e)}")

class APISettingsClaude(models.Model):
    api_key = EncryptedCharField(max_length=255, validators=[validate_claude_api_key])
    model_name = models.ForeignKey(ModelChoice, on_delete=models.SET_NULL, null=True, limit_choices_to={'provider': 'claude', 'is_active': True})
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=1000)

    def __str__(self):
        return f"API Settings Claude - {self.model_name.model_name if self.model_name else 'No model selected'}"

    class Meta:
        verbose_name_plural = "API Settings Claude"

class APISettingsGroq(models.Model):
    api_key = EncryptedCharField(max_length=255)
    model_name = models.ForeignKey(ModelChoice, on_delete=models.SET_NULL, null=True, limit_choices_to={'provider': 'groq', 'is_active': True})

    def __str__(self):
        return f"API Settings Groq - {self.model_name.model_name if self.model_name else 'No model selected'}"

    class Meta:
        verbose_name_plural = "API Settings Groq"

def validate_deepseek_api_key(value):
    client = OpenAI(api_key=value, base_url="https://api.deepseek.com/v1")
    try:
        # Спроба зробити тестовий запит
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=10
        )
    except Exception as e:
        raise ValidationError(f"Invalid DeepSeek API key: {str(e)}")

class APISettingsDeepSeek(models.Model):
    api_key = EncryptedCharField(max_length=255, validators=[validate_deepseek_api_key])
    model_name = models.ForeignKey(ModelChoice, on_delete=models.SET_NULL, null=True, limit_choices_to={'provider': 'deepseek', 'is_active': True})
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=1000)
    top_p = models.FloatField(default=1.0)
    frequency_penalty = models.FloatField(default=0.0)
    presence_penalty = models.FloatField(default=0.0)

    def __str__(self):
        return f"API Settings DeepSeek - {self.model_name.model_name if self.model_name else 'No model selected'}"

    class Meta:
        verbose_name_plural = "API Settings DeepSeek"


class AIAgentSettings(models.Model):
    """Налаштування AI агента для помічника користувачів"""
    user = models.OneToOneField(
        'auth.User', 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Якщо не вказано, то це глобальні налаштування за замовчуванням"
    )
    model_choice = models.ForeignKey(
        ModelChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'is_active': True},
        help_text="Модель AI для використання агентом"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Чи активований AI помічник"
    )
    enabled_for_all_pages = models.BooleanField(
        default=True,
        help_text="Чи показувати помічника на всіх сторінках"
    )
    
    class Meta:
        verbose_name = "AI Agent Settings"
        verbose_name_plural = "AI Agent Settings"
        
    def __str__(self):
        if self.user:
            return f"AI Agent Settings for {self.user.username}"
        return "Default AI Agent Settings"
    
    @classmethod
    def get_settings_for_user(cls, user):
        """Отримати налаштування для користувача або за замовчуванням"""
        try:
            # Спробувати знайти налаштування для користувача
            settings = cls.objects.get(user=user, is_active=True)
            return settings
        except cls.DoesNotExist:
            # Якщо немає налаштувань для користувача, повернути за замовчуванням
            try:
                return cls.objects.get(user__isnull=True, is_active=True)
            except cls.DoesNotExist:
                return None


class AIAssistantHistory(models.Model):
    """Історія запитів до AI помічника"""
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='ai_assistant_queries',
        help_text="Користувач, який зробив запит"
    )
    model_choice = models.ForeignKey(
        ModelChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Модель AI, яка була використана"
    )
    user_message = models.TextField(
        help_text="Повідомлення користувача"
    )
    ai_response = models.TextField(
        null=True,
        blank=True,
        help_text="Відповідь AI"
    )
    page_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="URL сторінки, на якій був зроблений запит"
    )
    page_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Тип сторінки (compliance, risk, incident, etc.)"
    )
    page_description = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Опис сторінки"
    )
    is_success = models.BooleanField(
        default=True,
        help_text="Чи був запит успішним"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Повідомлення про помилку, якщо запит не вдався"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Час створення запиту"
    )
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Час відповіді в мілісекундах"
    )
    input_tokens = models.IntegerField(
        null=True,
        blank=True,
        help_text="Кількість токенів у запиті (input tokens)"
    )
    output_tokens = models.IntegerField(
        null=True,
        blank=True,
        help_text="Кількість токенів у відповіді (output tokens)"
    )
    total_tokens = models.IntegerField(
        null=True,
        blank=True,
        help_text="Загальна кількість токенів"
    )
    
    class Meta:
        verbose_name = "AI Assistant History"
        verbose_name_plural = "AI Assistant History"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['page_type']),
        ]
    
    def __str__(self):
        user_msg_preview = self.user_message[:50] + '...' if len(self.user_message) > 50 else self.user_message
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {user_msg_preview}"
    
    @property
    def model_name(self):
        """Повернути назву моделі"""
        return self.model_choice.model_name if self.model_choice else "N/A"
    
    @property
    def provider(self):
        """Повернути провайдера моделі"""
        return self.model_choice.provider if self.model_choice else "N/A"