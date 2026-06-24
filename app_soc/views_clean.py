import json
import logging
import base64
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from .models import WazuhFIMAlert, WazuhAgent, WebhookClient, WebhookAuthConfig, AccessFIM, AnalysisConfig

logger = logging.getLogger(__name__)
