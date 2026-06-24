from django.core.management.base import BaseCommand
from app_risk.models import FinancialImpact, OperationalImpact, ReputationalImpact
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate impact levels with default data according to the methodology'

    def handle(self, *args, **options):
        self.stdout.write('Populating Financial Impact levels...')
        self.populate_financial_impacts()
        
        self.stdout.write('Populating Operational Impact levels...')
        self.populate_operational_impacts()
        
        self.stdout.write('Populating Reputational Impact levels...')
        self.populate_reputational_impacts()
        
        self.stdout.write(self.style.SUCCESS('Successfully populated all impact levels'))

    def populate_financial_impacts(self):
        """Populate Financial Impact levels according to Table 2"""
        financial_impacts = [
            {
                'name_uk': 'Високий',
                'name_en': 'High',
                'name_ru': 'Высокий',
                'description_uk': 'Значні фінансові втрати, що загрожують фінансовій стабільності',
                'description_en': 'Significant financial losses that threaten financial stability',
                'description_ru': 'Значительные финансовые потери, угрожающие финансовой стабильности',
                'min_value': Decimal('500000.00'),
                'max_value': Decimal('999999999.99'),
                'impact_value': Decimal('0.95'),
                'color': '#DC3545',
                'criteria_uk': 'Втрати понад 500 тис. грн, що загрожують фінансовій стабільності Товариства',
                'criteria_en': 'Losses over 500,000 UAH that threaten the Company\'s financial stability',
                'criteria_ru': 'Потери свыше 500 тыс. грн, угрожающие финансовой стабильности Общества',
                'examples_uk': 'Втрата коштів через шахрайські транзакції, штрафи від НБУ за порушення вимог, витрати на відновлення після ransomware',
                'examples_en': 'Loss of funds through fraudulent transactions, fines from NBU for violation of requirements, recovery costs after ransomware',
                'examples_ru': 'Потеря средств через мошеннические транзакции, штрафы от НБУ за нарушение требований, расходы на восстановление после ransomware'
            },
            {
                'name_uk': 'Середній',
                'name_en': 'Medium',
                'name_ru': 'Средний',
                'description_uk': 'Помірні фінансові втрати, що потребують додаткових ресурсів',
                'description_en': 'Moderate financial losses requiring additional resources',
                'description_ru': 'Умеренные финансовые потери, требующие дополнительных ресурсов',
                'min_value': Decimal('50000.00'),
                'max_value': Decimal('499999.99'),
                'impact_value': Decimal('0.70'),
                'color': '#FFC107',
                'criteria_uk': 'Втрати від 50 до 500 тис. грн, що потребують додаткових ресурсів',
                'criteria_en': 'Losses from 50,000 to 500,000 UAH requiring additional resources',
                'criteria_ru': 'Потери от 50 до 500 тыс. грн, требующие дополнительных ресурсов',
                'examples_uk': 'Витрати на модернізацію систем безпеки, компенсаційні виплати клієнтам',
                'examples_en': 'Costs for security system modernization, customer compensation payments',
                'examples_ru': 'Расходы на модернизацию систем безопасности, компенсационные выплаты клиентам'
            },
            {
                'name_uk': 'Низький',
                'name_en': 'Low',
                'name_ru': 'Низкий',
                'description_uk': 'Незначні фінансові втрати, покриваються операційним бюджетом',
                'description_en': 'Minor financial losses covered by operational budget',
                'description_ru': 'Незначительные финансовые потери, покрываемые операционным бюджетом',
                'min_value': Decimal('0.01'),
                'max_value': Decimal('49999.99'),
                'impact_value': Decimal('0.30'),
                'color': '#28A745',
                'criteria_uk': 'Втрати менше 50 тис. грн, покриваються операційним бюджетом',
                'criteria_en': 'Losses less than 50,000 UAH covered by operational budget',
                'criteria_ru': 'Потери менее 50 тыс. грн, покрываемые операционным бюджетом',
                'examples_uk': 'Витрати на незначні ремонти обладнання, дрібні штрафи',
                'examples_en': 'Costs for minor equipment repairs, small fines',
                'examples_ru': 'Расходы на незначительный ремонт оборудования, мелкие штрафы'
            },
            {
                'name_uk': 'Некритичний',
                'name_en': 'Non-critical',
                'name_ru': 'Некритичный',
                'description_uk': 'Відсутні фінансові втрати',
                'description_en': 'No financial losses',
                'description_ru': 'Отсутствие финансовых потерь',
                'min_value': Decimal('0.00'),
                'max_value': Decimal('0.00'),
                'impact_value': Decimal('0.00'),
                'color': '#6C757D',
                'criteria_uk': 'Відсутні фінансові втрати або втрати незначні',
                'criteria_en': 'No financial losses or losses are negligible',
                'criteria_ru': 'Отсутствие финансовых потерь или потери незначительны',
                'examples_uk': 'Відсутні фінансові наслідки',
                'examples_en': 'No financial consequences',
                'examples_ru': 'Отсутствие финансовых последствий'
            }
        ]
        
        for impact_data in financial_impacts:
            FinancialImpact.objects.get_or_create(
                name_uk=impact_data['name_uk'],
                defaults=impact_data
            )

    def populate_operational_impacts(self):
        """Populate Operational Impact levels according to Table 2"""
        operational_impacts = [
            {
                'name_uk': 'Високий',
                'name_en': 'High',
                'name_ru': 'Высокий',
                'description_uk': 'Простій критичних систем більше 4 годин або повна зупинка бізнес-процесів',
                'description_en': 'Critical systems downtime more than 4 hours or complete business process shutdown',
                'description_ru': 'Простой критических систем более 4 часов или полная остановка бизнес-процессов',
                'min_downtime_hours': Decimal('4.01'),
                'max_downtime_hours': Decimal('999.99'),
                'impact_value': Decimal('0.95'),
                'color': '#DC3545',
                'criteria_uk': 'Простій критичних систем більше 4 годин, повна зупинка бізнес-процесів',
                'criteria_en': 'Critical systems downtime more than 4 hours, complete business process shutdown',
                'criteria_ru': 'Простой критических систем более 4 часов, полная остановка бизнес-процессов',
                'examples_uk': 'Недоступність платіжної системи через DDoS-атаку, збій у системі автентифікації',
                'examples_en': 'Payment system unavailability due to DDoS attack, authentication system failure',
                'examples_ru': 'Недоступность платежной системы из-за DDoS-атаки, сбой в системе аутентификации'
            },
            {
                'name_uk': 'Середній',
                'name_en': 'Medium',
                'name_ru': 'Средний',
                'description_uk': 'Простій некритичних систем більше 8 годин або часткове обмеження операцій',
                'description_en': 'Non-critical systems downtime more than 8 hours or partial operation restrictions',
                'description_ru': 'Простой некритических систем более 8 часов или частичные ограничения операций',
                'min_downtime_hours': Decimal('2.01'),
                'max_downtime_hours': Decimal('8.00'),
                'impact_value': Decimal('0.70'),
                'color': '#FFC107',
                'criteria_uk': 'Простій некритичних систем від 2 до 8 годин, часткове обмеження операцій',
                'criteria_en': 'Non-critical systems downtime from 2 to 8 hours, partial operation restrictions',
                'criteria_ru': 'Простой некритических систем от 2 до 8 часов, частичные ограничения операций',
                'examples_uk': 'Тимчасові перебої в роботі допоміжних систем, обмеження функціональності',
                'examples_en': 'Temporary disruptions in auxiliary systems operation, functionality limitations',
                'examples_ru': 'Временные перебои в работе вспомогательных систем, ограничения функциональности'
            },
            {
                'name_uk': 'Низький',
                'name_en': 'Low',
                'name_ru': 'Низкий',
                'description_uk': 'Простій некритичних систем менше 2 годин або незначні перебої',
                'description_en': 'Non-critical systems downtime less than 2 hours or minor disruptions',
                'description_ru': 'Простой некритических систем менее 2 часов или незначительные перебои',
                'min_downtime_hours': Decimal('0.01'),
                'max_downtime_hours': Decimal('2.00'),
                'impact_value': Decimal('0.30'),
                'color': '#28A745',
                'criteria_uk': 'Простій некритичних систем менше 2 годин, незначні перебої',
                'criteria_en': 'Non-critical systems downtime less than 2 hours, minor disruptions',
                'criteria_ru': 'Простой некритических систем менее 2 часов, незначительные перебои',
                'examples_uk': 'Короткочасні перебої в роботі допоміжних сервісів',
                'examples_en': 'Short-term disruptions in auxiliary services operation',
                'examples_ru': 'Кратковременные перебои в работе вспомогательных сервисов'
            },
            {
                'name_uk': 'Некритичний',
                'name_en': 'Non-critical',
                'name_ru': 'Некритичный',
                'description_uk': 'Без простою систем',
                'description_en': 'No system downtime',
                'description_ru': 'Без простоя систем',
                'min_downtime_hours': Decimal('0.00'),
                'max_downtime_hours': Decimal('0.00'),
                'impact_value': Decimal('0.00'),
                'color': '#6C757D',
                'criteria_uk': 'Відсутність простою систем, операції не порушені',
                'criteria_en': 'No system downtime, operations not disrupted',
                'criteria_ru': 'Отсутствие простоя систем, операции не нарушены',
                'examples_uk': 'Відсутні операційні наслідки',
                'examples_en': 'No operational consequences',
                'examples_ru': 'Отсутствие операционных последствий'
            }
        ]
        
        for impact_data in operational_impacts:
            OperationalImpact.objects.get_or_create(
                name_uk=impact_data['name_uk'],
                defaults=impact_data
            )

    def populate_reputational_impacts(self):
        """Populate Reputational Impact levels according to Table 2"""
        reputational_impacts = [
            {
                'name_uk': 'Високий',
                'name_en': 'High',
                'name_ru': 'Высокий',
                'description_uk': 'Масштабний розголос, що призводить до значної втрати довіри',
                'description_en': 'Large-scale publicity leading to significant loss of trust',
                'description_ru': 'Масштабная огласка, приводящая к значительной потере доверия',
                'impact_value': Decimal('0.95'),
                'color': '#DC3545',
                'criteria_uk': 'Масштабний витік даних або тривала недоступність, що призводить до значної втрати довіри',
                'criteria_en': 'Large-scale data breach or prolonged unavailability leading to significant loss of trust',
                'criteria_ru': 'Масштабная утечка данных или длительная недоступность, приводящая к значительной потере доверия',
                'examples_uk': 'Витік даних клієнтів із негативним висвітленням у ЗМІ, тривала недоступність послуг',
                'examples_en': 'Customer data breach with negative media coverage, prolonged service unavailability',
                'examples_ru': 'Утечка данных клиентов с негативным освещением в СМИ, длительная недоступность услуг'
            },
            {
                'name_uk': 'Середній',
                'name_en': 'Medium',
                'name_ru': 'Средний',
                'description_uk': 'Тимчасові перебої або локальний витік даних із помірною реакцією клієнтів',
                'description_en': 'Temporary disruptions or local data breach with moderate customer response',
                'description_ru': 'Временные перебои или локальная утечка данных с умеренной реакцией клиентов',
                'impact_value': Decimal('0.70'),
                'color': '#FFC107',
                'criteria_uk': 'Тимчасові перебої або локальний витік даних із помірною реакцією клієнтів',
                'criteria_en': 'Temporary disruptions or local data breach with moderate customer response',
                'criteria_ru': 'Временные перебои или локальная утечка данных с умеренной реакцией клиентов',
                'examples_uk': 'Тимчасові перебої в роботі систем, локальні інциденти без широкого розголосу',
                'examples_en': 'Temporary system disruptions, local incidents without widespread publicity',
                'examples_ru': 'Временные перебои в работе систем, локальные инциденты без широкой огласки'
            },
            {
                'name_uk': 'Низький',
                'name_en': 'Low',
                'name_ru': 'Низкий',
                'description_uk': 'Незначні інциденти без широкого розголосу',
                'description_en': 'Minor incidents without widespread publicity',
                'description_ru': 'Незначительные инциденты без широкой огласки',
                'impact_value': Decimal('0.30'),
                'color': '#28A745',
                'criteria_uk': 'Незначні інциденти без широкого розголосу, мінімальний вплив на репутацію',
                'criteria_en': 'Minor incidents without widespread publicity, minimal impact on reputation',
                'criteria_ru': 'Незначительные инциденты без широкой огласки, минимальное влияние на репутацию',
                'examples_uk': 'Незначні технічні проблеми, які вирішуються швидко без публічності',
                'examples_en': 'Minor technical issues that are resolved quickly without publicity',
                'examples_ru': 'Незначительные технические проблемы, которые решаются быстро без публичности'
            },
            {
                'name_uk': 'Некритичний',
                'name_en': 'Non-critical',
                'name_ru': 'Некритичный',
                'description_uk': 'Без розголосу та впливу на репутацію',
                'description_en': 'No publicity and no impact on reputation',
                'description_ru': 'Без огласки и влияния на репутацию',
                'impact_value': Decimal('0.00'),
                'color': '#6C757D',
                'criteria_uk': 'Відсутність розголосу та впливу на репутацію Товариства',
                'criteria_en': 'No publicity and no impact on the Company\'s reputation',
                'criteria_ru': 'Отсутствие огласки и влияния на репутацию Общества',
                'examples_uk': 'Відсутні репутаційні наслідки',
                'examples_en': 'No reputational consequences',
                'examples_ru': 'Отсутствие репутационных последствий'
            }
        ]
        
        for impact_data in reputational_impacts:
            ReputationalImpact.objects.get_or_create(
                name_uk=impact_data['name_uk'],
                defaults=impact_data
            )
