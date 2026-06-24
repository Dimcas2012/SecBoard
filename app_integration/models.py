from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from encrypted_model_fields.fields import EncryptedCharField


class TelegramBot(models.Model):
    """Налаштування підключення до Telegram-бота."""

    name = models.CharField(_('Name'), max_length=100)
    bot_token = EncryptedCharField(_('Bot token'), max_length=500)
    bot_username = models.CharField(
        _('Bot username'),
        max_length=100,
        blank=True,
        help_text=_('Filled automatically after a successful connection test.'),
    )
    bot_id = models.BigIntegerField(_('Bot ID'), null=True, blank=True)
    default_chat_id = models.CharField(
        _('Default chat ID'),
        max_length=64,
        blank=True,
        help_text=_('Chat or channel ID for outbound notifications (optional).'),
    )
    use_webhook = models.BooleanField(
        _('Use webhook'),
        default=False,
        help_text=_('Receive updates via webhook instead of long polling.'),
    )
    webhook_secret = models.CharField(
        _('Webhook secret'),
        max_length=128,
        blank=True,
        help_text=_('Optional secret token for incoming webhook validation.'),
    )
    respond_to_start = models.BooleanField(
        _('Respond to /start'),
        default=True,
        help_text=_('Send a welcome message when a user sends /start to the bot.'),
    )
    start_message = models.TextField(
        _('Start message'),
        blank=True,
        help_text=_('Custom reply for /start. Leave empty to use the default welcome message.'),
    )
    is_active = models.BooleanField(_('Active'), default=True)
    description = models.TextField(_('Description'), blank=True)
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.CASCADE,
        related_name='telegram_bots',
        verbose_name=_('Company'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='telegram_bots',
        verbose_name=_('Created by'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_connection_check = models.DateTimeField(
        _('Last connection check'),
        null=True,
        blank=True,
    )
    last_connection_ok = models.BooleanField(_('Last connection OK'), default=False)

    class Meta:
        verbose_name = _('Telegram bot')
        verbose_name_plural = _('Telegram bots')
        ordering = ['name']

    def __str__(self):
        if self.bot_username:
            return f'{self.name} (@{self.bot_username})'
        return self.name

    @property
    def display_username(self):
        if self.bot_username:
            return f'@{self.bot_username}'
        return '—'


class TelegramAuthLink(models.Model):
    """One-time login link from Telegram that binds chat_id after SecBoard sign-in."""

    token = models.CharField(_('Token'), max_length=64, unique=True, db_index=True)
    bot = models.ForeignKey(
        TelegramBot,
        on_delete=models.CASCADE,
        related_name='auth_links',
        verbose_name=_('Telegram bot'),
    )
    chat_id = models.CharField(_('Telegram chat ID'), max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(_('Expires at'))
    used_at = models.DateTimeField(_('Used at'), null=True, blank=True)
    cabinet_user = models.ForeignKey(
        'app_cabinet.CabinetUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='telegram_auth_links',
        verbose_name=_('Cabinet user'),
    )

    class Meta:
        verbose_name = _('Telegram auth link')
        verbose_name_plural = _('Telegram auth links')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.bot.name} — chat {self.chat_id}'

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()


class AccessIntegration(models.Model):
    """Права доступу до модуля інтеграцій."""

    group = models.OneToOneField(
        'auth.Group',
        on_delete=models.CASCADE,
        related_name='access_integration',
        verbose_name=_('Group'),
    )
    has_access = models.BooleanField(_('Has access'), default=False)
    can_view_integrations = models.BooleanField(_('Can view integrations'), default=True)
    can_manage_integrations = models.BooleanField(_('Can manage integrations'), default=False)
    can_test_connections = models.BooleanField(_('Can test connections'), default=True)
    companies = models.ManyToManyField(
        'app_conf.Company',
        blank=True,
        related_name='access_integration',
        verbose_name=_('Companies'),
        help_text=_('Leave empty for access to all companies.'),
    )
    description = models.TextField(_('Description'), blank=True)

    class Meta:
        verbose_name = _('Access to Integrations')
        verbose_name_plural = _('Access to Integrations')

    def __str__(self):
        return f'{self.group.name} — {_("access")}: {self.has_access}'
