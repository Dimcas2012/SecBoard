from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app_tprm.models import QuestionnaireTemplate, Question


class Command(BaseCommand):
    help = 'Create default questionnaire templates for TPRM'

    def handle(self, *args, **options):
        user = User.objects.first()
        
        # Security Questionnaire Template
        security_template, created = QuestionnaireTemplate.objects.get_or_create(
            name='Security Assessment Questionnaire',
            category='security',
            defaults={
                'description': 'Comprehensive security assessment for third-party vendors',
                'is_active': True,
                'created_by': user
            }
        )

        if created:
            questions = [
                {
                    'question_text': 'Does the vendor have an information security policy?',
                    'question_type': 'yes_no',
                    'weight': 10,
                    'order': 1,
                    'is_required': True,
                    'correct_answer': 'yes',
                    'help_text': 'Verify if the vendor maintains a documented information security policy'
                },
                {
                    'question_text': 'Is the vendor ISO 27001 certified?',
                    'question_type': 'yes_no',
                    'weight': 15,
                    'order': 2,
                    'is_required': True,
                    'correct_answer': 'yes',
                    'help_text': 'Check for valid ISO 27001 certification'
                },
                {
                    'question_text': 'Does the vendor conduct regular security audits?',
                    'question_type': 'yes_no',
                    'weight': 10,
                    'order': 3,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Rate the vendor\'s encryption implementation',
                    'question_type': 'scale',
                    'weight': 10,
                    'order': 4,
                    'is_required': True,
                    'help_text': 'Consider encryption at rest, in transit, and key management practices'
                },
                {
                    'question_text': 'Does the vendor have incident response procedures?',
                    'question_type': 'yes_no',
                    'weight': 10,
                    'order': 5,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Rate the vendor\'s access control mechanisms',
                    'question_type': 'scale',
                    'weight': 10,
                    'order': 6,
                    'is_required': True
                },
                {
                    'question_text': 'Additional security observations',
                    'question_type': 'text',
                    'weight': 5,
                    'order': 7,
                    'is_required': False
                },
            ]
            
            for q_data in questions:
                Question.objects.create(template=security_template, **q_data)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Created Security template with {len(questions)} questions'))

        # Compliance Questionnaire Template
        compliance_template, created = QuestionnaireTemplate.objects.get_or_create(
            name='Compliance Assessment',
            category='compliance',
            defaults={
                'description': 'Regulatory compliance and data protection assessment',
                'is_active': True,
                'created_by': user
            }
        )

        if created:
            questions = [
                {
                    'question_text': 'Is the vendor GDPR compliant?',
                    'question_type': 'yes_no',
                    'weight': 15,
                    'order': 1,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Does the vendor have SOC 2 Type II certification?',
                    'question_type': 'yes_no',
                    'weight': 15,
                    'order': 2,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Rate the vendor\'s data privacy practices',
                    'question_type': 'scale',
                    'weight': 10,
                    'order': 3,
                    'is_required': True
                },
                {
                    'question_text': 'Does the vendor conduct employee background checks?',
                    'question_type': 'yes_no',
                    'weight': 5,
                    'order': 4,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Compliance concerns or notes',
                    'question_type': 'text',
                    'weight': 5,
                    'order': 5,
                    'is_required': False
                },
            ]
            
            for q_data in questions:
                Question.objects.create(template=compliance_template, **q_data)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Created Compliance template with {len(questions)} questions'))

        # Operational Questionnaire
        operational_template, created = QuestionnaireTemplate.objects.get_or_create(
            name='Operational Risk Assessment',
            category='operational',
            defaults={
                'description': 'Assessment of operational capabilities and business continuity',
                'is_active': True,
                'created_by': user
            }
        )

        if created:
            questions = [
                {
                    'question_text': 'Does the vendor have a business continuity plan?',
                    'question_type': 'yes_no',
                    'weight': 10,
                    'order': 1,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Rate the vendor\'s service availability/uptime',
                    'question_type': 'scale',
                    'weight': 10,
                    'order': 2,
                    'is_required': True
                },
                {
                    'question_text': 'Does the vendor have disaster recovery procedures?',
                    'question_type': 'yes_no',
                    'weight': 10,
                    'order': 3,
                    'is_required': True,
                    'correct_answer': 'yes'
                },
                {
                    'question_text': 'Rate the vendor\'s support and response time',
                    'question_type': 'scale',
                    'weight': 10,
                    'order': 4,
                    'is_required': True
                },
            ]
            
            for q_data in questions:
                Question.objects.create(template=operational_template, **q_data)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Created Operational template with {len(questions)} questions'))

        self.stdout.write(self.style.SUCCESS(f'\nTotal templates: {QuestionnaireTemplate.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total questions: {Question.objects.count()}'))

