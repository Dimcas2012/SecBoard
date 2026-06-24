from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db import connection
from .models import AccessPage, AccessQuiz


@receiver(pre_delete, sender=AccessPage)
def cleanup_accesspage_related_records(sender, instance, **kwargs):
    """Clean up related records in app_quiz_accesspage_companies table before deleting AccessPage"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM app_quiz_accesspage_companies 
                WHERE accesspage_id = %s
            """, [instance.id])
    except Exception:
        # If the table doesn't exist or there's an error, just continue
        pass


@receiver(pre_delete, sender=AccessQuiz)
def cleanup_accessquiz_related_records(sender, instance, **kwargs):
    """Clean up related records in app_quiz_accessquiz_companies table before deleting AccessQuiz"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM app_quiz_accessquiz_companies 
                WHERE accessquiz_id = %s
            """, [instance.id])
    except Exception:
        # If the table doesn't exist or there's an error, just continue
        pass
