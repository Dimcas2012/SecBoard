from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AppCifConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app_cif"
    verbose_name = _("Об'єкти критичної інфраструктури")
