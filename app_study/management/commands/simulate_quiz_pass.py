from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from app_study.models import Quiz, QuizAttempt, QuizAnswer, Question, Answer


class Command(BaseCommand):
    help = 'Simulate a successful quiz completion for a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email of the user',
            required=True,
        )
        parser.add_argument(
            '--quiz-title',
            type=str,
            help='Title of the quiz',
            required=True,
        )

    def handle(self, *args, **options):
        email = options['email']
        quiz_title = options['quiz_title']

        self.stdout.write(self.style.NOTICE(f'Starting quiz simulation...'))
        self.stdout.write(self.style.NOTICE(f'User email: {email}'))
        self.stdout.write(self.style.NOTICE(f'Quiz title: {quiz_title}'))

        # Find user by email
        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.SUCCESS(f'✓ Found user: {user.get_full_name() or user.username}'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ User with email "{email}" not found'))
            return

        # Find quiz by title
        try:
            quiz = Quiz.objects.get(title=quiz_title)
            self.stdout.write(self.style.SUCCESS(f'✓ Found quiz: {quiz.title}'))
            self.stdout.write(self.style.NOTICE(f'  Passing score: {quiz.passing_score}'))
        except Quiz.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Quiz with title "{quiz_title}" not found'))
            
            # Show available quizzes
            available_quizzes = Quiz.objects.all()
            if available_quizzes.exists():
                self.stdout.write(self.style.WARNING('\nAvailable quizzes:'))
                for q in available_quizzes:
                    self.stdout.write(f'  - {q.title}')
            return

        # Get all questions for this quiz
        questions = quiz.questions.all()
        if not questions.exists():
            self.stdout.write(self.style.ERROR('✗ Quiz has no questions'))
            return

        self.stdout.write(self.style.NOTICE(f'  Questions count: {questions.count()}'))

        # Check if there are previous attempts
        previous_attempts = QuizAttempt.objects.filter(user=user, quiz=quiz)
        if previous_attempts.exists():
            self.stdout.write(self.style.WARNING(f'\n⚠ User has {previous_attempts.count()} previous attempt(s)'))
            for i, attempt in enumerate(previous_attempts, 1):
                status = '✓ PASSED' if attempt.score >= quiz.passing_score else '✗ FAILED'
                completed_status = 'Completed' if attempt.completed else 'Not completed'
                self.stdout.write(f'  Attempt {i}: {attempt.score} points - {status} ({completed_status})')

        # Create a new attempt
        attempt = QuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            completed=False,
            score=0
        )
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created quiz attempt (ID: {attempt.id})'))

        # Answer all questions correctly to ensure passing
        correct_answers_count = 0
        total_score = 0

        for question in questions:
            # Get the first correct answer for this question
            correct_answer = question.answers.filter(is_correct=True).first()
            
            if correct_answer:
                # Create quiz answer
                quiz_answer = QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    answer=correct_answer
                )
                total_score += correct_answer.score
                correct_answers_count += 1
                self.stdout.write(f'  ✓ Question {question.id}: {question.text[:50]}... (Score: {correct_answer.score})')
            else:
                self.stdout.write(self.style.WARNING(f'  ⚠ Question {question.id} has no correct answer!'))

        # Update attempt with final score and mark as completed
        attempt.score = total_score
        attempt.completed = True
        attempt.completed_at = timezone.now()
        attempt.save()

        # Calculate result
        is_passed = attempt.score >= quiz.passing_score
        status_icon = '✓' if is_passed else '✗'
        status_text = 'PASSED' if is_passed else 'FAILED'
        status_style = self.style.SUCCESS if is_passed else self.style.ERROR

        self.stdout.write('\n' + '='*60)
        self.stdout.write(status_style(f'{status_icon} Quiz {status_text}'))
        self.stdout.write('='*60)
        self.stdout.write(f'Final Score: {attempt.score}/{total_score}')
        self.stdout.write(f'Passing Score: {quiz.passing_score}')
        self.stdout.write(f'Correct Answers: {correct_answers_count}/{questions.count()}')
        self.stdout.write(f'Completed At: {attempt.completed_at.strftime("%d.%m.%Y %H:%M:%S")}')
        self.stdout.write('='*60)

        if is_passed:
            self.stdout.write(self.style.SUCCESS('\n✓ Successfully simulated quiz completion!'))
        else:
            self.stdout.write(self.style.ERROR('\n✗ Quiz was not passed (score too low)'))

