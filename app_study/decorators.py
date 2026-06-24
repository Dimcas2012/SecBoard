# SecBoard\SecBoard\app_study\decorators.py
from django.contrib.auth.decorators import user_passes_test
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Quiz

import logging

logger = logging.getLogger(__name__)


def group_required(group_name):
    print('check_group group_name ', group_name)
    def check_group(user):
        print('check_group user ', user)
        return user.groups.filter(name=group_name).exists()

    return user_passes_test(check_group, login_url='unauthorized')


def user_has_quiz_access(view_func):
    @wraps(view_func)
    @user_passes_test(lambda u: u.is_authenticated, login_url='unauthorized')
    def wrapper(request, quiz_id, *args, **kwargs):
        quiz = get_object_or_404(Quiz, id=quiz_id)
        
        if not quiz.has_user_access(request.user):
            raise PermissionDenied("User does not have access to this quiz.")

        return view_func(request, quiz_id, *args, **kwargs)

    return wrapper