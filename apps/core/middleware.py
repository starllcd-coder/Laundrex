import traceback as tb
from django.utils import timezone

from .models import ErrorLog


class ErrorLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        try:
            user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            branch_code = request.session.get("active_branch", "") if hasattr(request, "session") else ""
            ErrorLog.objects.create(
                level="ERROR",
                message=str(exception)[:255],
                path=request.path[:255],
                method=request.method[:10],
                branch_code=branch_code,
                user=user,
                traceback="".join(tb.format_exception(type(exception), exception, exception.__traceback__))[:8000],
                created_at=timezone.now(),
            )
        except Exception:
            pass
        return None
