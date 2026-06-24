from django.core.management.base import BaseCommand
from app_risk.models import FinancialImpact, OperationalImpact, ReputationalImpact


class Command(BaseCommand):
    help = 'Add English and Russian names to existing impact levels'

    def handle(self, *args, **options):
        self.stdout.write('Adding English and Russian names to impact levels...')
        
        # Update Financial Impact levels
        self.update_financial_impacts()
        
        # Update Operational Impact levels
        self.update_operational_impacts()
        
        # Update Reputational Impact levels
        self.update_reputational_impacts()
        
        self.stdout.write(self.style.SUCCESS('Successfully updated impact level names!'))

    def update_financial_impacts(self):
        """Update Financial Impact levels with English and Russian names"""
        financial_updates = [
            {
                'name_uk': 'Некритичний',
                'name_en': 'Non-critical',
                'name_ru': 'Некритичный',
                'min_value': 0,
                'max_value': 0
            },
            {
                'name_uk': 'Низький',
                'name_en': 'Low',
                'name_ru': 'Низкий',
                'min_value': 0.01,
                'max_value': 49999.99
            },
            {
                'name_uk': 'Середній',
                'name_en': 'Medium',
                'name_ru': 'Средний',
                'min_value': 50000.00,
                'max_value': 499999.99
            },
            {
                'name_uk': 'Високий',
                'name_en': 'High',
                'name_ru': 'Высокий',
                'min_value': 500000.00,
                'max_value': 999999999.99
            }
        ]
        
        for update_data in financial_updates:
            try:
                impact = FinancialImpact.objects.get(
                    min_value=update_data['min_value'],
                    max_value=update_data['max_value']
                )
                impact.name_en = update_data['name_en']
                impact.name_ru = update_data['name_ru']
                impact.save()
                self.stdout.write(f'Updated Financial Impact: {impact.name_uk} -> EN: {impact.name_en}, RU: {impact.name_ru}')
            except FinancialImpact.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Financial Impact not found for range {update_data["min_value"]}-{update_data["max_value"]}'))

    def update_operational_impacts(self):
        """Update Operational Impact levels with English and Russian names"""
        operational_updates = [
            {
                'name_uk': 'Некритичний',
                'name_en': 'Non-critical',
                'name_ru': 'Некритичный',
                'min_downtime_hours': 0,
                'max_downtime_hours': 0
            },
            {
                'name_uk': 'Низький',
                'name_en': 'Low',
                'name_ru': 'Низкий',
                'min_downtime_hours': 0.01,
                'max_downtime_hours': 2.00
            },
            {
                'name_uk': 'Середній',
                'name_en': 'Medium',
                'name_ru': 'Средний',
                'min_downtime_hours': 2.01,
                'max_downtime_hours': 8.00
            },
            {
                'name_uk': 'Високий',
                'name_en': 'High',
                'name_ru': 'Высокий',
                'min_downtime_hours': 4.01,
                'max_downtime_hours': 999.99
            }
        ]
        
        for update_data in operational_updates:
            try:
                impact = OperationalImpact.objects.get(
                    min_downtime_hours=update_data['min_downtime_hours'],
                    max_downtime_hours=update_data['max_downtime_hours']
                )
                impact.name_en = update_data['name_en']
                impact.name_ru = update_data['name_ru']
                impact.save()
                self.stdout.write(f'Updated Operational Impact: {impact.name_uk} -> EN: {impact.name_en}, RU: {impact.name_ru}')
            except OperationalImpact.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Operational Impact not found for range {update_data["min_downtime_hours"]}-{update_data["max_downtime_hours"]} hours'))

    def update_reputational_impacts(self):
        """Update Reputational Impact levels with English and Russian names"""
        reputational_updates = [
            {
                'name_uk': 'Некритичний',
                'name_en': 'Non-critical',
                'name_ru': 'Некритичный',
                'impact_value': 0.00
            },
            {
                'name_uk': 'Низький',
                'name_en': 'Low',
                'name_ru': 'Низкий',
                'impact_value': 0.30
            },
            {
                'name_uk': 'Середній',
                'name_en': 'Medium',
                'name_ru': 'Средний',
                'impact_value': 0.70
            },
            {
                'name_uk': 'Високий',
                'name_en': 'High',
                'name_ru': 'Высокий',
                'impact_value': 0.95
            }
        ]
        
        for update_data in reputational_updates:
            try:
                impact = ReputationalImpact.objects.get(
                    impact_value=update_data['impact_value']
                )
                impact.name_en = update_data['name_en']
                impact.name_ru = update_data['name_ru']
                impact.save()
                self.stdout.write(f'Updated Reputational Impact: {impact.name_uk} -> EN: {impact.name_en}, RU: {impact.name_ru}')
            except ReputationalImpact.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Reputational Impact not found for value {update_data["impact_value"]}'))
