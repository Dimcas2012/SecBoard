from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app_tprm.models import QuestionnaireTemplate, Question


class Command(BaseCommand):
    help = 'Create example branching questionnaire template'

    def handle(self, *args, **options):
        user = User.objects.first()
        
        # Development & Third-Party Assessment (Branching Example)
        template, created = QuestionnaireTemplate.objects.get_or_create(
            name='Development & Third-Party Services Assessment',
            category='security',
            defaults={
                'description': 'Conditional questionnaire: questions branch based on internal vs third-party development',
                'is_active': True,
                'created_by': user
            }
        )

        if not created:
            self.stdout.write(self.style.WARNING('Template already exists, skipping...'))
            return

        # ROOT QUESTION
        q1 = Question.objects.create(
            template=template,
            question_text='Чи є у вас внутрішня розробка ПЗ?',
            question_type='yes_no',
            weight=5,
            order=1,
            is_required=True,
            help_text='Визначає наявність власної команди розробки'
        )
        
        # BRANCH 1: IF YES (internal development)
        q2_yes = Question.objects.create(
            template=template,
            question_text='Скільки розробників у вашій команді?',
            question_type='scale',
            weight=5,
            order=2,
            parent_question=q1,
            show_if_answer='yes',
            is_required=True,
            help_text='1 = 1-5 розробників, 5 = 50+ розробників'
        )
        
        q3_yes = Question.objects.create(
            template=template,
            question_text='Чи проводите ви code review?',
            question_type='yes_no',
            weight=10,
            order=3,
            parent_question=q1,
            show_if_answer='yes',
            is_required=True,
            correct_answer='yes'
        )
        
        q4_yes = Question.objects.create(
            template=template,
            question_text='Чи використовуєте SAST/DAST інструменти?',
            question_type='yes_no',
            weight=10,
            order=4,
            parent_question=q1,
            show_if_answer='yes',
            is_required=True,
            correct_answer='yes'
        )
        
        # BRANCH 2: IF NO (third-party development)
        q2_no = Question.objects.create(
            template=template,
            question_text='Хто є вашим основним постачальником розробки?',
            question_type='text',
            weight=5,
            order=5,
            parent_question=q1,
            show_if_answer='no',
            is_required=True,
            help_text='Назва компанії або постачальника'
        )
        
        q3_no = Question.objects.create(
            template=template,
            question_text='Чи підписано NDA з постачальником?',
            question_type='yes_no',
            weight=15,
            order=6,
            parent_question=q1,
            show_if_answer='no',
            is_required=True,
            correct_answer='yes'
        )
        
        q4_no = Question.objects.create(
            template=template,
            question_text='Чи проводиться security assessment постачальника?',
            question_type='yes_no',
            weight=15,
            order=7,
            parent_question=q1,
            show_if_answer='no',
            is_required=True,
            correct_answer='yes'
        )
        
        q5_no = Question.objects.create(
            template=template,
            question_text='Оцініть якість документації від постачальника',
            question_type='scale',
            weight=5,
            order=8,
            parent_question=q1,
            show_if_answer='no',
            is_required=True,
            help_text='1 = погано, 5 = відмінно'
        )
        
        # SUB-BRANCH: If third-party AND no security assessment
        q6_no_no = Question.objects.create(
            template=template,
            question_text='КРИТИЧНО: Чому не проводиться security assessment?',
            question_type='text',
            weight=20,
            order=9,
            parent_question=q4_no,
            show_if_answer='no',
            is_required=True,
            help_text='Поясніть причину відсутності security assessment'
        )
        
        # COMMON QUESTIONS (shown for both branches)
        q_common = Question.objects.create(
            template=template,
            question_text='Чи є процес управління вразливостями?',
            question_type='yes_no',
            weight=10,
            order=10,
            is_required=True,
            correct_answer='yes'
        )
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created branching template with {template.questions.count()} questions'))
        self.stdout.write(self.style.SUCCESS(f'  - Root questions: 1'))
        self.stdout.write(self.style.SUCCESS(f'  - Branch "YES" (internal): 3 questions'))
        self.stdout.write(self.style.SUCCESS(f'  - Branch "NO" (third-party): 4 questions'))
        self.stdout.write(self.style.SUCCESS(f'  - Sub-branch: 1 question'))
        self.stdout.write(self.style.SUCCESS(f'  - Common questions: 1'))

