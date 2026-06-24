# from django import template
# from app_risk.models import AccessRiskAssessment
#
# register = template.Library()
#
# @register.filter
# def access_risk_assessment_show_link(groups):
#     return AccessRiskAssessment.objects.filter(group__in=groups, show_link=True).exists()