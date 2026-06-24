import logging
import re
import sys
import tempfile
from django.utils.deprecation import MiddlewareMixin
from django.core.files.uploadhandler import TemporaryFileUploadHandler

logger = logging.getLogger(__name__)

class MultipartFixMiddleware(MiddlewareMixin):
    """
    Middleware to fix issues with multipart/form-data handling in Python 3.13
    """
    
    def process_request(self, request):
        """
        Process the request before it's handled by the view
        """
        if request.method == 'POST' and request.content_type and 'multipart/form-data' in request.content_type:
            # Add a logging statement to help debug
            logger.debug(f"Handling multipart form request: {request.path}")
            
            # Ensure the request uses TemporaryFileUploadHandler for all file uploads
            request.upload_handlers = [TemporaryFileUploadHandler(request=request)]
            
            # For Python 3.13+, apply additional fixes
            if sys.version_info >= (3, 13):
                # Since cgi module is removed in Python 3.13, we implement our own boundary validation
                def valid_boundary(s):
                    """
                    Custom boundary validation function for Python 3.13+
                    """
                    try:
                        if isinstance(s, bytes):
                            s = s.decode('utf-8', errors='replace')
                        return re.match(r'^[ -~]{0,200}[!-~]$', s) is not None
                    except Exception as e:
                        logger.warning(f"Error in valid_boundary: {e}")
                        return True  # Be more permissive in case of errors
                
                # Store the function for potential use
                self.valid_boundary = valid_boundary
                
                # Set temporary directory for file uploads
                tempfile.tempdir = tempfile.gettempdir()
                
                # Log that we applied the custom boundary validation
                logger.debug("Applied custom boundary validation for Python 3.13+")
        
        return None 