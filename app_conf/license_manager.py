# SecBoard\app_conf\license_manager.py
"""
License Management System
"""

from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
import logging

from .license_crypto import LicenseCrypto, LicenseKeyFormatter
from .hardware_binding import HardwareFingerprint

logger = logging.getLogger(__name__)


class LicenseValidator:
    """
    License validator.
    Checks all license aspects: signature, hardware, expiration, limits.
    """
    
    @staticmethod
    def validate_license(license_obj):
        """
        Full validation of a license object.

        Args:
            license_obj: SecureLicense model instance

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        try:
            # Check 1: Is the license blocked (remote blocking from the server)
            if hasattr(license_obj, 'is_blocked') and license_obj.is_blocked:
                block_reason = getattr(license_obj, 'block_reason', '')
                error_msg = f"License is blocked by server"
                if block_reason:
                    error_msg += f": {block_reason}"
                return False, error_msg
            
            # Check 2: Is the license active in the database
            if not license_obj.is_active:
                return False, "License is not active"
            
            # Check 2: Obtaining and validating license data
            license_data = license_obj.get_license_data()
            if not license_data:
                return False, "License data validation failed"
            
            # Check 3: Validity
            expiration_str = license_data.get('expiration_date')
            if not expiration_str:
                return False, "License expiration date not found"
            
            try:
                expiration_date = datetime.fromisoformat(expiration_str).date()
                if expiration_date < timezone.now().date():
                    license_obj.is_active = False
                    license_obj.save()
                    return False, f"License expired on {expiration_date}"
            except ValueError:
                return False, "Invalid expiration date format"
            
            # Check 4: Server ID binding (Hash of Hardware ID + HTTP_HOST)
            stored_server_id = license_data.get('hardware_id')  # On the server this is stored as hardware_id, but it is now the Server ID
            current_server_id = HardwareFingerprint.get_server_id()
            
            if stored_server_id != current_server_id:
                logger.critical(
                    f"Server ID mismatch! License Server ID: {stored_server_id[:16]}..., "
                    f"Current Server ID: {current_server_id[:16]}..."
                )
                return False, "Server ID binding validation failed"
            
            # Check 5: User limit
            max_users = license_data.get('max_users', 0)
            active_users_count = User.objects.filter(is_active=True).count()
            
            if active_users_count > max_users:
                return False, f"User limit exceeded ({active_users_count}/{max_users})"
            
            # Check 6: Counter of failed attempts
            if license_obj.failed_validations > 10:
                logger.critical(
                    f"License blocked due to too many failed validation attempts: "
                    f"{license_obj.failed_validations}"
                )
                return False, "License blocked due to security violations"
            
            # Updating the timestamp of the last validation
            license_obj.last_validated = timezone.now()
            license_obj.failed_validations = 0
            license_obj.save(update_fields=['last_validated', 'failed_validations'])
            
            logger.info(f"License validation SUCCESS for company: {license_data.get('company')}")
            return True, None
            
        except Exception as e:
            logger.error(f"License validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"
    
    # Module access check disabled
    # @staticmethod
    # def check_module_access(license_obj, module_name):
    #     """
    # Checking access to a specific module
    #     
    #     Args:
    # license_obj: SecureLicense model object
    # module_name (str): Name of the module (eg: 'risk', 'compliance', 'gdpr')
    #         
    #     Returns:
    # bool: True if access is allowed, False if not
    #     """
    #     try:
    # # First, we validate the license
    #         is_valid, error = LicenseValidator.validate_license(license_obj)
    #         if not is_valid:
    #             logger.warning(f"Module access denied for {module_name}: {error}")
    #             return False
    #         
    # # We get license data
    #         license_data = license_obj.get_license_data()
    #         if not license_data:
    #             return False
    #         
    # # We check access to the module
    #         modules = license_data.get('modules', {})
    #         has_access = modules.get(module_name, False)
    #         
    #         if has_access:
    #             logger.info(f"Module access GRANTED: {module_name}")
    #         else:
    #             logger.warning(f"Module access DENIED: {module_name}")
    #         
    #         return has_access
    #         
    #     except Exception as e:
    #         logger.error(f"Module access check error for {module_name}: {str(e)}")
    #         return False
    
    @staticmethod
    def get_days_remaining(license_obj):
        """
        Get the number of days until license expiration.

        Args:
            license_obj: SecureLicense model instance

        Returns:
            int: Number of days (0 if expired or on error)
        """
        try:
            license_data = license_obj.get_license_data()
            if not license_data:
                return 0
            
            expiration_str = license_data.get('expiration_date')
            if not expiration_str:
                return 0
            
            expiration_date = datetime.fromisoformat(expiration_str).date()
            today = timezone.now().date()
            
            delta = (expiration_date - today).days
            return max(0, delta)
            
        except Exception as e:
            logger.error(f"Error calculating days remaining: {str(e)}")
            return 0


class LicenseActivator:
    """
    License activator.
    Handles activation of new licenses.
    """
    
    @staticmethod
    def activate_license(license_key, request=None):
        """
        Activate a license key.

        Args:
            license_key (str): License key
            request: HTTP request object (optional, for IP logging)

        Returns:
            tuple: (success: bool, license_obj or None, error_message: str or None)
        """
        from app_conf.models import SecureLicense, LicenseActivation
        
        try:
            # Key normalization
            clean_key = LicenseKeyFormatter.normalize_license_key(license_key)
            
            # Step 1: Data and signature extraction
            license_data, signature = LicenseCrypto.extract_license_data(clean_key)
            
            if not license_data or not signature:
                error = "Failed to extract license data or signature"
                logger.error(f"License activation failed: {error}")
                LicenseActivator._log_activation(None, False, error, request)
                return False, None, error
            
            # Step 2: Signature validation
            if not LicenseCrypto.verify_license_signature(license_data, signature):
                error = "License signature verification failed"
                logger.error(f"License activation failed: {error}")
                LicenseActivator._log_activation(None, False, error, request)
                return False, None, error
            
            # Step 3: Check required fields
            required_fields = ['company', 'hardware_id', 'expiration_date', 'max_users']  # 'modules' removed
            missing_fields = [field for field in required_fields if field not in license_data]
            if missing_fields:
                error = f"Missing required fields: {', '.join(missing_fields)}"
                logger.error(f"License activation failed: {error}")
                LicenseActivator._log_activation(None, False, error, request)
                return False, None, error
            
            # Step 3.5: Checking the lock status on the license server (BEFORE checking the Server ID)
            # This allows you to block activation even if the Server ID does not match
            from app_conf.license_server_api import LicenseServerAPI
            validation_data = None
            is_valid = None
            server_validation_failed = False
            logger.info("Checking license status on server before activation...")
            try:
                # We use validate_online to check the status on the server
                is_valid, validation_data = LicenseServerAPI.validate_online(clean_key)
                logger.info(f"Server validation result: is_valid={is_valid}, validation_data={validation_data}")
                
                # CRITICAL VALIDATION: If validation_data contains blocking information
                # This should be the FIRST check, regardless of the value of is_valid
                if validation_data:
                    server_is_blocked = validation_data.get('is_blocked', False)
                    server_block_reason = validation_data.get('block_reason', '')
                    
                    logger.info(f"Checking block status: server_is_blocked={server_is_blocked}, block_reason={server_block_reason}")
                    
                    if server_is_blocked:
                        error_msg = f"License is blocked on server: {server_block_reason}" if server_block_reason else "License is blocked on server"
                        logger.error(f"License activation BLOCKED: {error_msg}")
                        LicenseActivator._log_activation(None, False, error_msg, request)
                        return False, None, error_msg
                    
                    # Check if there is a validation error with the word "blocked"
                    error_msg_from_server = validation_data.get('error', '')
                    if error_msg_from_server and 'blocked' in error_msg_from_server.lower():
                        logger.error(f"License activation BLOCKED (from error message): {error_msg_from_server}")
                        LicenseActivator._log_activation(None, False, error_msg_from_server, request)
                        return False, None, error_msg_from_server
                
                # SECOND CHECK: If is_valid is True but validation_data contains is_blocked: True
                # This can happen if the server returned 200 with valid: True but is_blocked: True (it shouldn't be, but we're checking)
                if is_valid is True and validation_data and validation_data.get('is_blocked'):
                    error_msg = validation_data.get('error', f"License is blocked: {validation_data.get('block_reason', 'Blocked by server')}")
                    logger.error(f"License activation BLOCKED (is_valid=True but is_blocked=True): {error_msg}")
                    LicenseActivator._log_activation(None, False, error_msg, request)
                    return False, None, error_msg
                
                # THIRD CHECK: If the validation returned False (not None), the license is invalid
                # If the server returns is_valid=False, it means that the license is invalid or blocked
                # We BLOCK activation in any case
                if is_valid is False:
                    error_msg = validation_data.get('error', 'License validation failed on server') if validation_data else 'License is not valid on server'
                    logger.error(f"License activation BLOCKED (is_valid=False from server): {error_msg}")
                    server_validation_failed = True
                    # We block activation immediately if the server returned is_valid=False
                    LicenseActivator._log_activation(None, False, error_msg, request)
                    return False, None, error_msg
                
                # FOURTH CHECK: If is_valid is None, the server is unavailable (offline mode)
                # BUT: even in offline mode, you need to check whether there was an error in validation_data
                if is_valid is None:
                    # If validation_data contains information about blocking, we still block activation
                    if validation_data and validation_data.get('is_blocked'):
                        error_msg = validation_data.get('error', f"License is blocked: {validation_data.get('block_reason', 'Blocked by server')}")
                        logger.error(f"License activation BLOCKED (offline mode but blocked): {error_msg}")
                        LicenseActivator._log_activation(None, False, error_msg, request)
                        return False, None, error_msg
                    logger.warning("License server unreachable (offline mode) - activation will proceed without server validation")
                    
            except Exception as e:
                # If it was not possible to contact the server, we warn but allow activation (offline mode)
                # BUT: if there is validation_data with blocking, we still block it
                logger.warning(f"Exception during server validation: {str(e)}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                
                # Check if validation_data is locked even after exception
                if validation_data and validation_data.get('is_blocked'):
                    error_msg = validation_data.get('error', f"License is blocked: {validation_data.get('block_reason', 'Blocked by server')}")
                    logger.error(f"License activation BLOCKED (exception but blocked): {error_msg}")
                    LicenseActivator._log_activation(None, False, error_msg, request)
                    return False, None, error_msg
                
                logger.warning("License activation will proceed, but server status check was skipped")
            
            # Step 4: Checking Server ID binding
            # Server ID = hash (Hardware ID + HTTP_HOST from the first request)
            license_server_id = license_data.get('hardware_id', '').strip()  # On the server this is stored as hardware_id, but it is now the Server ID
            current_server_id = HardwareFingerprint.get_server_id().strip()
            
            # Diagnostic information
            logger.info(f"License Server ID: {license_server_id[:16]}... (length: {len(license_server_id)})")
            logger.info(f"Current Server ID: {current_server_id[:16]}... (length: {len(current_server_id)})")
            
            if license_server_id != current_server_id:
                error_msg = (
                    f"Server ID mismatch!\n"
                    f"License Server ID: {license_server_id[:16]}... (length: {len(license_server_id)})\n"
                    f"Current Server ID: {current_server_id[:16]}... (length: {len(current_server_id)})\n"
                    f"This license is bound to a different server.\n\n"
                    f"Please ensure you are using the correct Server ID that was provided when the license was generated."
                )
                logger.error(f"License activation failed: {error_msg}")
                LicenseActivator._log_activation(None, False, error_msg, request)
                return False, None, error_msg
            
            # Step 5: Deactivate all previous licenses
            SecureLicense.objects.all().update(is_active=False)
            
            # Step 6: Generate a search hash
            import hashlib
            license_key_hash = hashlib.sha256(clean_key.encode('utf-8')).hexdigest()
            
            # CRITICAL CHECK BEFORE CREATING A LICENSE:
            # If validation_data contains blocking information, BLOCK the activation
            # This is the last opportunity to block activation before saving to the database
            if validation_data:
                server_is_blocked = validation_data.get('is_blocked', False)
                server_block_reason = validation_data.get('block_reason', '')
                
                if server_is_blocked:
                    error_msg = f"License is blocked on server: {server_block_reason}" if server_block_reason else "License is blocked on server"
                    logger.error(f"License activation BLOCKED (final check before save): {error_msg}")
                    LicenseActivator._log_activation(None, False, error_msg, request)
                    return False, None, error_msg
                
                # Check if there is a validation error with the word "blocked"
                error_msg_from_server = validation_data.get('error', '')
                if error_msg_from_server and 'blocked' in error_msg_from_server.lower():
                    logger.error(f"License activation BLOCKED (final check from error message): {error_msg_from_server}")
                    LicenseActivator._log_activation(None, False, error_msg_from_server, request)
                    return False, None, error_msg_from_server
            
            # Step 7: Create or update a license
            # IMPORTANT: the signature must be complete (up to 1024 characters for RSA-4096)
            # We use license_key_hash to search, because license_key is now a TextField
            # Store Server ID in hardware_fingerprint (for compatibility with existing code)
            
            # Synchronize the blocking status from the server (if there was validation)
            # IMPORTANT: First check the blocking status, then set is_active
            is_blocked_from_server = False
            block_reason_from_server = ''
            
            if validation_data:
                is_blocked_from_server = validation_data.get('is_blocked', False)
                block_reason_from_server = validation_data.get('block_reason', '') or ''
            
            # Make sure block_reason is always a string (not None)
            if block_reason_from_server is None:
                block_reason_from_server = ''
            
            defaults = {
                    'license_key': clean_key,  # Full key (can be > 768 characters)
                    'signature': signature,  # Full signature with extract_license_data
                    'hardware_fingerprint': current_server_id,  # Now it's Server ID instead of Hardware ID
                    'encrypted_data': license_data,  # JSONField
                'is_active': not is_blocked_from_server,  # Activate only if NOT blocked
                    'last_validated': timezone.now(),
                    'failed_validations': 0,
                'is_blocked': is_blocked_from_server,  # Synchronize lock status
                'block_reason': block_reason_from_server,  # Synchronize the blocking reason
                }
            
            license_obj, created = SecureLicense.objects.update_or_create(
                license_key_hash=license_key_hash,
                defaults=defaults
            )

            try:
                # Must pass license_key_hash so the report is v3 and HMAC-bound to this key;
                # otherwise middleware verify (allow_create=False) can fail after restart.
                HardwareFingerprint.create_signed_hardware_report(license_key_hash)
            except Exception as hw_err:
                logger.warning(f"Could not create hardware report on activation: {hw_err}")
            
            # Step 5: Logging successful activation
            action = "activated" if created else "updated"
            logger.info(
                f"License {action} successfully! "
                f"Company: {license_data.get('company')}, "
                f"Expires: {license_data.get('expiration_date')}"
            )
            
            LicenseActivator._log_activation(license_obj, True, "", request)
            
            return True, license_obj, None
            
        except Exception as e:
            error_msg = f"License activation error: {str(e)}"
            logger.error(error_msg)
            LicenseActivator._log_activation(None, False, error_msg, request)
            return False, None, error_msg
    
    @staticmethod
    def _log_activation(license_obj, success, error_message, request=None):
        """
        Log an activation attempt.

        Args:
            license_obj: License object (or None)
            success (bool): Whether activation succeeded
            error_message (str): Error message
            request: HTTP request (optional)
        """
        try:
            from app_conf.models import LicenseActivation
            
            # Obtaining an IP address
            ip_address = None
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0]
                else:
                    ip_address = request.META.get('REMOTE_ADDR')
            
            # Gathering information about the server
            server_info = HardwareFingerprint.get_fingerprint_info()
            
            # Create a record
            LicenseActivation.objects.create(
                license=license_obj,
                activation_date=timezone.now(),
                hardware_fingerprint=server_info['fingerprint'],
                ip_address=ip_address or '0.0.0.0',
                success=success,
                error_message=error_message,
                server_info=server_info
            )
            
        except Exception as e:
            logger.error(f"Failed to log activation: {str(e)}")


# Module access controller disabled
# class ModuleAccessController:
#     """
# Platform module access controller
#     """
#     
# # Definition of available modules
#     AVAILABLE_MODULES = {
#         'risk': {
#             'name': 'Risk Assessment',
# 'name_uk': 'Risk Assessment',
#             'app': 'app_risk',
#             'description': 'Risk assessment and management module'
#         },
#         'compliance': {
#             'name': 'Compliance Management',
# 'name_uk': 'Compliance Management',
#             'app': 'app_compliance',
#             'description': 'Compliance and regulatory management'
#         },
#         'gdpr': {
#             'name': 'GDPR',
#             'name_uk': 'GDPR',
#             'app': 'app_gdpr',
#             'description': 'GDPR compliance and data protection'
#         },
#         'gophish': {
#             'name': 'Phishing Simulation',
# 'name_uk': 'Phishing Simulation',
#             'app': 'app_gophish',
#             'description': 'Security awareness and phishing campaigns'
#         },
#         'tprm': {
#             'name': 'Third-Party Risk',
# 'name_uk': 'Third Party Risks',
#             'app': 'app_tprm',
#             'description': 'Third-party risk management'
#         },
#         'incident': {
#             'name': 'Incident Management',
# 'name_uk': 'Incident Management',
#             'app': 'app_incident',
#             'description': 'Security incident tracking and response'
#         },
#         'asset': {
#             'name': 'Asset Management',
# 'name_uk': 'Asset Management',
#             'app': 'app_asset',
#             'description': 'IT asset inventory and management'
#         },
#     }
#     
#     @classmethod
#     def get_enabled_modules(cls, license_obj):
#         """
# Obtaining a list of enabled modules according to the license
#         
#         Args:
# license_obj: SecureLicense model object
#             
#         Returns:
# list: List of enabled modules with details
#         """
#         enabled = []
#         
#         try:
#             license_data = license_obj.get_license_data()
#             if not license_data:
#                 return enabled
#             
#             modules = license_data.get('modules', {})
#             
#             for module_key, module_info in cls.AVAILABLE_MODULES.items():
#                 if modules.get(module_key, False):
#                     enabled.append({
#                         'key': module_key,
#                         'name': module_info['name'],
#                         'name_uk': module_info['name_uk'],
#                         'app': module_info['app'],
#                         'description': module_info['description'],
#                     })
#             
#             logger.info(f"Enabled modules: {', '.join([m['key'] for m in enabled])}")
#             
#         except Exception as e:
#             logger.error(f"Error getting enabled modules: {str(e)}")
#         
#         return enabled
#     
#     @classmethod
#     def check_access(cls, license_obj, module_name):
#         """
# Quick module access check
#         
#         Args:
# license_obj: SecureLicense model object
# module_name (str): Name of the module
#             
#         Returns:
# bool: True if access is allowed
#         """
#         return LicenseValidator.check_module_access(license_obj, module_name)


class LicenseStatusChecker:
    """
    License status checker.
    """
    
    @staticmethod
    def get_license_status():
        """
        Get detailed license status.

        Returns:
            dict: License status with all details
        """
        from app_conf.models import SecureLicense
        
        try:
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            
            if not license_obj:
                return {
                    'valid': False,
                    'error': 'No active license found',
                    'status': 'NOT_FOUND'
                }
            
            # License validation
            is_valid, error = LicenseValidator.validate_license(license_obj)
            
            if not is_valid:
                return {
                    'valid': False,
                    'error': error,
                    'status': 'INVALID'
                }
            
            # Receiving data
            license_data = license_obj.get_license_data()
            days_remaining = LicenseValidator.get_days_remaining(license_obj)
            # enabled_modules = ModuleAccessController.get_enabled_modules(license_obj)  # Disabled
            
            # Determination of status by days
            if days_remaining <= 0:
                status = 'EXPIRED'
            elif days_remaining <= 7:
                status = 'EXPIRING_SOON'
            elif days_remaining <= 30:
                status = 'EXPIRING'
            else:
                status = 'ACTIVE'
            
            return {
                'valid': True,
                'status': status,
                'company': license_data.get('company'),
                'expiration_date': license_data.get('expiration_date'),
                'days_remaining': days_remaining,
                'max_users': license_data.get('max_users'),
                'current_users': User.objects.filter(is_active=True).count(),
                # 'enabled_modules': enabled_modules,  # Disabled
                'last_validated': license_obj.last_validated.isoformat() if license_obj.last_validated else None,
            }
            
        except Exception as e:
            logger.error(f"Error getting license status: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'status': 'ERROR'
            }

