from django.core.management.base import BaseCommand

from app_integration.models import TelegramBot
from app_integration.telegram_client import TelegramAPIError, get_updates
from app_integration.telegram_handlers import process_telegram_update


class Command(BaseCommand):
    help = 'Process pending Telegram updates via long polling (for local development).'

    def add_arguments(self, parser):
        parser.add_argument('--bot-id', type=int, help='TelegramBot primary key')
        parser.add_argument('--once', action='store_true', help='Process one batch and exit')

    def handle(self, *args, **options):
        queryset = TelegramBot.objects.filter(is_active=True, respond_to_start=True)
        if options['bot_id']:
            queryset = queryset.filter(pk=options['bot_id'])

        if not queryset.exists():
            self.stdout.write(self.style.WARNING('No active bots with respond_to_start enabled.'))
            return

        processed_total = 0
        while True:
            batch_processed = 0
            for bot in queryset:
                try:
                    updates = get_updates(bot.bot_token, timeout=0)
                except TelegramAPIError as exc:
                    self.stderr.write(f'{bot.name}: {exc}')
                    continue

                for update in updates:
                    update_id = update.get('update_id')
                    if process_telegram_update(bot, update):
                        self.stdout.write(self.style.SUCCESS(
                            f'{bot.name}: processed /start (update_id={update_id})',
                        ))
                    else:
                        self.stdout.write(f'{bot.name}: ignored update_id={update_id}')
                    batch_processed += 1

            processed_total += batch_processed
            if options['once'] or batch_processed == 0:
                break

        self.stdout.write(self.style.SUCCESS(f'Done. Processed {processed_total} update(s).'))
