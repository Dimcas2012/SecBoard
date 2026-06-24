# app_conf/log_handlers/database_handler.py
import logging
import traceback
from django.utils.timezone import now
from django.core.exceptions import PermissionDenied
from django.db import transaction

class DatabaseLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()

    def emit(self, record):
        # Import here to prevent circular import
        from .models import LogEntry, ErrorLog

        try:
            # Get the request from the record if available
            request = getattr(record, 'request', None)
            request_path = getattr(request, 'path', None) if request else None
            user = getattr(request, 'user', None) if request else None
            user_str = str(user) if user and user.is_authenticated else None

            # Create the formatted message
            msg = self.format(record)

            # Get stack trace if available
            trace = None
            if record.exc_info:
                trace = '\n'.join(traceback.format_exception(*record.exc_info))

            # Create log entry
            try:
                with transaction.atomic():
                    LogEntry.objects.create(
                        timestamp=now(),
                        level=record.levelname,
                        logger_name=record.name,
                        message=msg,
                        trace=trace,
                        request_path=request_path,
                        user=user_str
                    )

                    # Create error log for ERROR and CRITICAL levels
                    if record.levelno >= logging.ERROR:
                        ErrorLog.objects.create(
                            timestamp=now(),
                            error_type=record.levelname,
                            error_message=msg,
                            stack_trace=trace or '',
                            request_path=request_path,
                            request_method=getattr(request, 'method', None) if request else None,
                            user=user_str
                        )
            except PermissionDenied:
                pass
            except Exception as e:
                print(f"Database logging failed: {str(e)}")

        except Exception as e:
            print(f"Error in DatabaseLogHandler: {str(e)}")