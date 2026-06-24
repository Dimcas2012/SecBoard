#  SecBoard\SecBoard\app_suib\decorators.py
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import Http404
from .models import RegisterDocs, RelatedDocs


def file_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required")

        doc_id = kwargs.get('doc_id')
        try:
            # Спробуємо знайти документ в RegisterDocs
            doc = RegisterDocs.objects.filter(
                id=doc_id,
                groups__in=request.user.groups.all()
            ).first()

            if not doc:
                # Якщо не знайшли в RegisterDocs, шукаємо в RelatedDocs
                doc = RelatedDocs.objects.filter(
                    id=doc_id,
                    groups__in=request.user.groups.all()
                ).first()

            if not doc:
                raise Http404("Document not found or access denied")

            # Додаємо документ до request для подальшого використання
            request.accessed_document = doc
            return view_func(request, *args, **kwargs)

        except (RegisterDocs.DoesNotExist, RelatedDocs.DoesNotExist):
            raise Http404("Document not found")

    return _wrapped_view