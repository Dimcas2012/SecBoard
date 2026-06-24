from django.core.management.base import BaseCommand
from app_risk.models import FinancialImpact, OperationalImpact, ReputationalImpact


class Command(BaseCommand):
    help = 'Add English and Russian descriptions, criteria, and examples to impact levels'

    def handle(self, *args, **options):
        self.stdout.write('Adding English and Russian descriptions to impact levels...')
        
        # Update Financial Impact descriptions
        self.update_financial_descriptions()
        
        # Update Operational Impact descriptions
        self.update_operational_descriptions()
        
        # Update Reputational Impact descriptions
        self.update_reputational_descriptions()
        
        self.stdout.write(self.style.SUCCESS('Successfully updated impact level descriptions!'))

    def update_financial_descriptions(self):
        """Update Financial Impact levels with English and Russian descriptions"""
        financial_updates = [
            {
                'name_uk': 'Некритичний',
                'description_uk': 'Мінімальні фінансові втрати',
                'description_en': 'Minimal financial losses',
                'description_ru': 'Минимальные финансовые потери',
                'criteria_uk': 'Втрати до 0 UAH',
                'criteria_en': 'Losses up to 0 UAH',
                'criteria_ru': 'Потери до 0 UAH',
                'examples_uk': 'Немає фінансових втрат',
                'examples_en': 'No financial losses',
                'examples_ru': 'Нет финансовых потерь'
            },
            {
                'name_uk': 'Низький',
                'description_uk': 'Низькі фінансові втрати',
                'description_en': 'Low financial losses',
                'description_ru': 'Низкие финансовые потери',
                'criteria_uk': 'Втрати від 0.01 до 49,999.99 UAH',
                'criteria_en': 'Losses from 0.01 to 49,999.99 UAH',
                'criteria_ru': 'Потери от 0.01 до 49,999.99 UAH',
                'examples_uk': 'Втрата невеликої суми грошей, мінімальні витрати на відновлення',
                'examples_en': 'Loss of small amount of money, minimal recovery costs',
                'examples_ru': 'Потеря небольшой суммы денег, минимальные затраты на восстановление'
            },
            {
                'name_uk': 'Середній',
                'description_uk': 'Середні фінансові втрати',
                'description_en': 'Medium financial losses',
                'description_ru': 'Средние финансовые потери',
                'criteria_uk': 'Втрати від 50,000 до 499,999.99 UAH',
                'criteria_en': 'Losses from 50,000 to 499,999.99 UAH',
                'criteria_ru': 'Потери от 50,000 до 499,999.99 UAH',
                'examples_uk': 'Значні фінансові втрати, витрати на відновлення систем',
                'examples_en': 'Significant financial losses, system recovery costs',
                'examples_ru': 'Значительные финансовые потери, затраты на восстановление систем'
            },
            {
                'name_uk': 'Високий',
                'description_uk': 'Високі фінансові втрати',
                'description_en': 'High financial losses',
                'description_ru': 'Высокие финансовые потери',
                'criteria_uk': 'Втрати від 500,000 UAH і більше',
                'criteria_en': 'Losses from 500,000 UAH and more',
                'criteria_ru': 'Потери от 500,000 UAH и более',
                'examples_uk': 'Критичні фінансові втрати, банкрутство, закриття бізнесу',
                'examples_en': 'Critical financial losses, bankruptcy, business closure',
                'examples_ru': 'Критические финансовые потери, банкротство, закрытие бизнеса'
            }
        ]
        
        for update_data in financial_updates:
            impact = FinancialImpact.get_by_display_name(update_data['name_uk'])
            if impact:
                impact.description = update_data.get('description_en') or impact.description
                impact.criteria = update_data.get('criteria_en') or impact.criteria
                impact.examples = update_data.get('examples_en') or impact.examples
                impact.save()
                self.stdout.write(f'Updated Financial Impact descriptions: {impact.get_name()}')
            else:
                self.stdout.write(self.style.WARNING(f'Financial Impact not found: {update_data["name_uk"]}'))

    def update_operational_descriptions(self):
        """Update Operational Impact levels with English and Russian descriptions"""
        operational_updates = [
            {
                'name_uk': 'Некритичний',
                'description_uk': 'Мінімальні операційні перебої',
                'description_en': 'Minimal operational disruptions',
                'description_ru': 'Минимальные операционные сбои',
                'criteria_uk': 'Простої до 0 годин',
                'criteria_en': 'Downtime up to 0 hours',
                'criteria_ru': 'Простои до 0 часов',
                'examples_uk': 'Немає операційних перебоїв',
                'examples_en': 'No operational disruptions',
                'examples_ru': 'Нет операционных сбоев'
            },
            {
                'name_uk': 'Низький',
                'description_uk': 'Низькі операційні перебої',
                'description_en': 'Low operational disruptions',
                'description_ru': 'Низкие операционные сбои',
                'criteria_uk': 'Простої від 0.01 до 2 годин',
                'criteria_en': 'Downtime from 0.01 to 2 hours',
                'criteria_ru': 'Простои от 0.01 до 2 часов',
                'examples_uk': 'Короткі перебої в роботі, незначні затримки',
                'examples_en': 'Short work disruptions, minor delays',
                'examples_ru': 'Короткие сбои в работе, незначительные задержки'
            },
            {
                'name_uk': 'Середній',
                'description_uk': 'Середні операційні перебої',
                'description_en': 'Medium operational disruptions',
                'description_ru': 'Средние операционные сбои',
                'criteria_uk': 'Простої від 2.01 до 8 годин',
                'criteria_en': 'Downtime from 2.01 to 8 hours',
                'criteria_ru': 'Простои от 2.01 до 8 часов',
                'examples_uk': 'Значні перебої в роботі, втрата робочого дня',
                'examples_en': 'Significant work disruptions, loss of working day',
                'examples_ru': 'Значительные сбои в работе, потеря рабочего дня'
            },
            {
                'name_uk': 'Високий',
                'description_uk': 'Високі операційні перебої',
                'description_en': 'High operational disruptions',
                'description_ru': 'Высокие операционные сбои',
                'criteria_uk': 'Простої від 4.01 годин і більше',
                'criteria_en': 'Downtime from 4.01 hours and more',
                'criteria_ru': 'Простои от 4.01 часов и более',
                'examples_uk': 'Критичні перебої в роботі, зупинка виробництва',
                'examples_en': 'Critical work disruptions, production shutdown',
                'examples_ru': 'Критические сбои в работе, остановка производства'
            }
        ]
        
        for update_data in operational_updates:
            impact = OperationalImpact.get_by_display_name(update_data['name_uk'])
            if impact:
                impact.description = update_data.get('description_en') or impact.description
                impact.criteria = update_data.get('criteria_en') or impact.criteria
                impact.examples = update_data.get('examples_en') or impact.examples
                impact.save()
                self.stdout.write(f'Updated Operational Impact descriptions: {impact.get_name()}')
            else:
                self.stdout.write(self.style.WARNING(f'Operational Impact not found: {update_data["name_uk"]}'))

    def update_reputational_descriptions(self):
        """Update Reputational Impact levels with English and Russian descriptions"""
        reputational_updates = [
            {
                'name_uk': 'Некритичний',
                'description_uk': 'Мінімальна репутаційна шкода',
                'description_en': 'Minimal reputational damage',
                'description_ru': 'Минимальный репутационный ущерб',
                'criteria_uk': 'Репутаційна шкода 0%',
                'criteria_en': 'Reputational damage 0%',
                'criteria_ru': 'Репутационный ущерб 0%',
                'examples_uk': 'Немає репутаційної шкоди',
                'examples_en': 'No reputational damage',
                'examples_ru': 'Нет репутационного ущерба'
            },
            {
                'name_uk': 'Низький',
                'description_uk': 'Низька репутаційна шкода',
                'description_en': 'Low reputational damage',
                'description_ru': 'Низкий репутационный ущерб',
                'criteria_uk': 'Репутаційна шкода 30%',
                'criteria_en': 'Reputational damage 30%',
                'criteria_ru': 'Репутационный ущерб 30%',
                'examples_uk': 'Незначні негативні відгуки, тимчасове зниження довіри',
                'examples_en': 'Minor negative feedback, temporary loss of trust',
                'examples_ru': 'Незначительные негативные отзывы, временная потеря доверия'
            },
            {
                'name_uk': 'Середній',
                'description_uk': 'Середня репутаційна шкода',
                'description_en': 'Medium reputational damage',
                'description_ru': 'Средний репутационный ущерб',
                'criteria_uk': 'Репутаційна шкода 70%',
                'criteria_en': 'Reputational damage 70%',
                'criteria_ru': 'Репутационный ущерб 70%',
                'examples_uk': 'Значні негативні відгуки, втрата клієнтів',
                'examples_en': 'Significant negative feedback, loss of customers',
                'examples_ru': 'Значительные негативные отзывы, потеря клиентов'
            },
            {
                'name_uk': 'Високий',
                'description_uk': 'Висока репутаційна шкода',
                'description_en': 'High reputational damage',
                'description_ru': 'Высокий репутационный ущерб',
                'criteria_uk': 'Репутаційна шкода 95%',
                'criteria_en': 'Reputational damage 95%',
                'criteria_ru': 'Репутационный ущерб 95%',
                'examples_uk': 'Критична репутаційна шкода, банкрутство бренду',
                'examples_en': 'Critical reputational damage, brand bankruptcy',
                'examples_ru': 'Критический репутационный ущерб, банкротство бренда'
            }
        ]
        
        for update_data in reputational_updates:
            try:
                impact = ReputationalImpact.objects.get(name_uk=update_data['name_uk'])
                impact.description_en = update_data['description_en']
                impact.description_ru = update_data['description_ru']
                impact.criteria_en = update_data['criteria_en']
                impact.criteria_ru = update_data['criteria_ru']
                impact.examples_en = update_data['examples_en']
                impact.examples_ru = update_data['examples_ru']
                impact.save()
                self.stdout.write(f'Updated Reputational Impact descriptions: {impact.name_uk}')
            except ReputationalImpact.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Reputational Impact not found: {update_data["name_uk"]}'))
