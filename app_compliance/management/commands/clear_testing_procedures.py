"""
Django management command для очищення Testing Procedure у всіх контролів
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from app_compliance.models import Control


class Command(BaseCommand):
    help = 'Очищує поле testing_procedure у всіх контролів'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показати що буде зроблено без фактичного виконання',
        )
        parser.add_argument(
            '--framework',
            type=int,
            help='ID конкретного framework (опціонально)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        framework_id = options.get('framework')
        
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('  ОЧИЩЕННЯ TESTING PROCEDURE'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        # Базовий queryset
        controls = Control.objects.all()
        
        # Фільтр за framework якщо вказано
        if framework_id:
            controls = controls.filter(category__framework_id=framework_id)
            self.stdout.write(f'Фільтр: Framework ID = {framework_id}')
        
        # Підрахунок контролів з непорожніми testing_procedure
        controls_with_tp = controls.exclude(testing_procedure='').exclude(testing_procedure__isnull=True)
        total_count = controls_with_tp.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ Всі Testing Procedure вже очищені!'))
            return
        
        self.stdout.write(f'\nЗнайдено контролів з Testing Procedure: {total_count}')
        
        # Показати приклади
        self.stdout.write('\nПриклади контролів що будуть очищені:')
        for control in controls_with_tp[:5]:
            tp_preview = control.testing_procedure[:80] + '...' if len(control.testing_procedure) > 80 else control.testing_procedure
            self.stdout.write(f'  • {control.code} - {control.name}')
            self.stdout.write(f'    TP: {tp_preview}')
        
        if total_count > 5:
            self.stdout.write(f'  ... і ще {total_count - 5} контролів\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠ DRY RUN MODE - зміни НЕ будуть застосовані'))
            self.stdout.write(self.style.WARNING('Запустіть без --dry-run для фактичного очищення\n'))
            return
        
        # Підтвердження
        self.stdout.write(self.style.WARNING(f'\n⚠ УВАГА: Буде очищено {total_count} Testing Procedure!'))
        confirm = input('Продовжити? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('\n✗ Операцію скасовано користувачем'))
            return
        
        # Виконання очищення
        try:
            with transaction.atomic():
                self.stdout.write('\n' + self.style.WARNING('Очищення Testing Procedure...'))
                
                updated_count = controls_with_tp.update(testing_procedure='')
                
                self.stdout.write(self.style.SUCCESS(f'\n✓ Успішно очищено {updated_count} Testing Procedure!'))
                
                # Перевірка
                remaining = controls.exclude(testing_procedure='').exclude(testing_procedure__isnull=True).count()
                if remaining > 0:
                    self.stdout.write(self.style.WARNING(f'⚠ Залишилось непорожніх: {remaining}'))
                else:
                    self.stdout.write(self.style.SUCCESS('✓ Всі Testing Procedure очищені'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Помилка: {str(e)}'))
            raise
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('  ЗАВЕРШЕНО'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))

