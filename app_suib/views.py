#  SecBoard\SecBoard\app_suib\views.py
import pytz
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
import logging
from django.shortcuts import render
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")



def get_server_time(request):
    user_timezone = request.session.get('user_timezone', 'UTC')
    server_time = timezone.now().astimezone(pytz.timezone(user_timezone))
    formatted_time = server_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    return JsonResponse({'server_time': formatted_time})

@require_POST
@login_required
@csrf_protect
def set_user_timezone(request):
    timezone = request.POST.get('timezone')
    if timezone:
        request.session['user_timezone'] = timezone
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

def error_page(request):
    error_message = request.GET.get('error_message', 'An unknown error occurred.')
    return render(request, 'app_suib/error.html', {'error_message': error_message})

def get_criticality(self):
    highest_criticality = max(
        [level for level in [self.confidentiality, self.integrity, self.availability] if level is not None],
        key=lambda x: x.cost if x else 0,
        default=None
    )

    if highest_criticality:
        return {
            'text': highest_criticality.critical_name_uk,
            'cost': highest_criticality.cost,
            'color': highest_criticality.color
        }
    else:
        return {
            'text': 'Not defined',
            'cost': 0,
            'color': '#000000'
        }



