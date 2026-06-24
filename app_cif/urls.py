from django.urls import path

from . import views
from .api import viewsets

app_name = "app_cif"

urlpatterns = [
    path("", views.cif_dashboard, name="dashboard"),
    path("objects/", views.cif_object_list, name="cif_object_list"),
    path("objects/create/", views.cif_object_create, name="cif_object_create"),
    path("objects/<int:pk>/", views.cif_object_detail, name="cif_object_detail"),
    path("objects/<int:pk>/passport/", views.cif_passport_edit, name="cif_passport_edit"),
    path("objects/<int:pk>/passport/approve/", views.cif_passport_approve, name="cif_passport_approve"),
    path("objects/<int:pk>/protection-plan/", views.cif_protection_plan_edit, name="cif_protection_plan_edit"),
    path("objects/<int:pk>/generate-report/", views.cif_generate_report, name="cif_generate_report"),
    path("api/cif/objects/", viewsets.CIFObjectListCreateAPIView.as_view(), name="api_cif_object_list"),
    path("api/cif/objects/<int:pk>/", viewsets.CIFObjectRetrieveUpdateAPIView.as_view(), name="api_cif_object_detail"),
    path("api/cif/objects/<int:pk>/passport/", viewsets.CIFObjectPassportAPIView.as_view(), name="api_cif_object_passport"),
    path(
        "api/cif/objects/<int:pk>/protection-plan/",
        viewsets.CIFObjectProtectionPlanAPIView.as_view(),
        name="api_cif_object_protection_plan",
    ),
    path(
        "api/cif/objects/<int:pk>/generate-report/",
        viewsets.CIFObjectGenerateReportAPIView.as_view(),
        name="api_cif_generate_report",
    ),
    path("api/cif/dashboard/", viewsets.CIFDashboardAPIView.as_view(), name="api_cif_dashboard"),
]
