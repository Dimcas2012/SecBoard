from html import escape

from django.db.models import Max
from django.urls import reverse
from django.utils.translation import gettext as _

from app_study.models import Quiz, QuizAttempt

from .telegram_tasks import _build_not_linked_reply_text, get_cabinet_user_for_telegram
from .utils import get_public_base_url


def get_quiz_status_for_cabinet_user(cabinet_user):
    user = cabinet_user.user
    all_quizzes = Quiz.objects.filter(is_active=True).prefetch_related(
        'companies', 'cabinet_groups', 'cabinet_users',
    )
    accessible_quizzes = [quiz for quiz in all_quizzes if quiz.has_user_access(user)]
    quiz_status = []
    for quiz in accessible_quizzes:
        attempts = QuizAttempt.objects.filter(user=user, quiz=quiz)
        completed_attempts = attempts.filter(completed=True)
        passed_attempts = completed_attempts.filter(score__gte=quiz.passing_score)
        in_progress = attempts.filter(completed=False).exists()
        latest_completed = completed_attempts.order_by('-completed_at').first()
        quiz_status.append({
            'title': quiz.title,
            'is_passed': passed_attempts.exists(),
            'needs_retake': completed_attempts.exists() and not passed_attempts.exists(),
            'in_progress': in_progress and not passed_attempts.exists(),
            'not_started': not attempts.exists(),
            'best_score': attempts.aggregate(Max('score'))['score__max'],
            'latest_score': latest_completed.score if latest_completed else None,
            'passing_score': quiz.passing_score,
        })
    return quiz_status


def _quiz_status_label(quiz):
    passing = quiz['passing_score']
    if quiz['is_passed']:
        if quiz['best_score'] is not None:
            return _('Passed (%(score)s/%(passing)s)') % {
                'score': quiz['best_score'],
                'passing': passing,
            }
        return _('Passed')
    if quiz['needs_retake']:
        if quiz['latest_score'] is not None:
            return _('Failed (%(score)s/%(passing)s)') % {
                'score': quiz['latest_score'],
                'passing': passing,
            }
        return _('Failed')
    if quiz['in_progress']:
        return _('In progress')
    return _('New')


def _get_learning_hub_link():
    base = get_public_base_url()
    path = reverse('learning_hub')
    return f'{base}{path}' if base else path


def _html(text):
    return escape(text, quote=False)


def _not_passed_header(count):
    label = _('Not passed (%(n)s):') % {'n': count}
    return f'🔴 <b>{_html(label)}</b>'


def _not_passed_line(quiz):
    label = _quiz_status_label(quiz)
    return f'🔴   • <b>{_html(quiz["title"])}</b> — {_html(label)}'


def build_training_reply_text(bot, chat_id):
    cabinet_user = get_cabinet_user_for_telegram(bot, chat_id)
    if not cabinet_user:
        return _build_not_linked_reply_text(_('Training'), chat_id)

    quiz_status = get_quiz_status_for_cabinet_user(cabinet_user)
    learning_hub_url = _get_learning_hub_link()
    lines = [
        f'<b>{_html(_("Training"))}</b>',
        '',
    ]
    if not quiz_status:
        lines.append(_html(_('You have no assigned tests.')))
        lines.append('')
        lines.append(_html(_('Open Learning Hub: %(url)s') % {'url': learning_hub_url}))
        return '\n'.join(lines), 'HTML'

    not_passed = [quiz for quiz in quiz_status if not quiz['is_passed']]
    passed = [quiz for quiz in quiz_status if quiz['is_passed']]

    if not_passed:
        lines.append(_not_passed_header(len(not_passed)))
        for quiz in not_passed[:10]:
            lines.append(_not_passed_line(quiz))
        if len(not_passed) > 10:
            lines.append(f'🔴 {_html(_("  … and %(n)s more") % {"n": len(not_passed) - 10})}')
        lines.append('')

    if passed:
        passed_header = _('Passed (%(n)s):') % {'n': len(passed)}
        lines.append(f'✅ {_html(passed_header)}')
        for quiz in passed[:10]:
            label = _quiz_status_label(quiz)
            lines.append(f'  • {_html(quiz["title"])} — {_html(label)}')
        if len(passed) > 10:
            lines.append(_html(_('  … and %(n)s more') % {'n': len(passed) - 10}))
        lines.append('')

    if not not_passed and not passed:
        lines.append(_html(_('You have no assigned tests.')))
        lines.append('')

    lines.append(_html(_('Open Learning Hub: %(url)s') % {'url': learning_hub_url}))
    return '\n'.join(lines), 'HTML'
