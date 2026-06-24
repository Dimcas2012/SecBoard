# SecBoard\app_conf\license_middleware.py
"""
License Middleware
"""

from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils import timezone
from datetime import timedelta
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

# Cross-module RSA key-hash pin.
#
# SHA-256 of the RSA public key PEM returned by LicenseCrypto._get_public_key_pem().
# Empty ('') in source/dev — the check is skipped for uncompiled builds.
# Populated by the build pipeline (obfuscate_cython_only.py Step 2.5b) so that
# replacing license_crypto.so with an attacker-controlled key ALSO requires
# patching and recompiling license_middleware.so.  This turns a single-file swap
# into a multi-file, multi-recompile operation and breaks the "rename .py →
# replace .so" shortcut.
#
# If this is empty in a compiled build the middleware will raise RuntimeError at
# startup — an incorrectly prepared build will fail loudly rather than silently.
_EXPECTED_CRYPTO_KEY_HASH = ''


class SecureLicenseMiddleware:
    """
    Middleware for automatic license verification
    
    Validates the license before each request and blocks access
    if the license is invalid or expired.
    """
    
    # URLs that do not require license verification
    EXEMPT_URLS = [
        '/admin/login/',
        '/secboard_admin/login/',
        '/app_cabinet/login/',
        '/accounts/login/',
        '/static/',
        '/media/',
        '/license/expired/',
        '/license/activate/',
        '/about/license/activate/',  # URL via app_conf
        '/license/blocked/',
        '/status/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self._validation_cache = {}
        self._last_check = None
        self._first_host_saved = False
    
    def _path_exempt_from_license_check(self, path):
        """
        Return True if this path must not run full license + hardware checks.

        i18n_patterns() prepends /<language>/ (e.g. /uk/about/...), so
        startswith('/about/license/activate/') misses /uk/about/license/activate/.
        Those requests must stay exempt so activation works and the page
        does not show 'Hardware integrity verification failed' before the
        view runs.
        """
        if any(path.startswith(url) for url in self.EXEMPT_URLS):
            return True
        if 'about/license/activate/' in path:
            return True
        if 'app_conf/license/activate/' in path:
            return True
        return False
    
    def __call__(self, request):
        # Saving the first HTTP_HOST for the uniqueness of the Hardware ID
        self._save_first_host(request)
        
        # We skip the excluded paths
        if self._path_exempt_from_license_check(request.path):
            return self.get_response(request)
        
        # License Validation (with Caching for Performance)
        is_valid, error_msg = self._validate_license_cached(request)
        
        if not is_valid:
            logger.warning(f"License validation failed: {error_msg}")
            
            # We get detailed information about the error
            error_details = self._get_error_details(request, error_msg)
            
            # Redirection to the license expiration page
            return render(request, 'license_expired.html', {
                'error_message': error_msg,
                'error_details': error_details,
                'support_email': 'support@secboard.online',
            }, status=403)
        
        # Add the license data to the request
        license_obj = self._get_current_license()
        request.license = license_obj
        
        # Module access check disabled
        # Validate module access based on URL
        # if license_obj:
        #     module_access_error = self._check_module_access_by_url(request, license_obj)
        #     if module_access_error:
        #         from django.contrib import messages
        #         from django.shortcuts import redirect
        #         messages.warning(request, module_access_error)
        #         return redirect('dashboard')
        
        response = self.get_response(request)
        return response
    
    def _save_first_host(self, request):
        """Store the first HTTP_HOST for Hardware ID uniqueness"""
        if self._first_host_saved:
            return
        
        try:
            from django.conf import settings
            
            host = request.get_host()
            if not host or host in ('testserver', 'localhost', '127.0.0.1'):
                # We skip the test hosts
                return
            
            # The path to the file to save
            base_dir = getattr(settings, 'BASE_DIR', '')
            if not base_dir:
                return
            
            install_file = Path(base_dir) / '.secboard_first_host'
            
            # If the file already exists, do not overwrite it
            if install_file.exists():
                self._first_host_saved = True
                return
            
            # Save HTTP_HOST
            try:
                install_file.parent.mkdir(parents=True, exist_ok=True)
                with open(install_file, 'w') as f:
                    f.write(host)
                install_file.chmod(0o600)  # Only for the owner
                self._first_host_saved = True
                logger.info(f"Saved first HTTP_HOST for installation ID: {host}")
            except Exception as e:
                logger.warning(f"Failed to save first HTTP_HOST: {str(e)}")
        except Exception as e:
            logger.debug(f"Could not save first host: {str(e)}")
    
    def _get_cache_ttl(self):
        """Full crypto verification runs once every LICENSE_CHECK_INTERVAL seconds."""
        from django.conf import settings as _s
        return timedelta(seconds=getattr(_s, 'LICENSE_CHECK_INTERVAL', 60))

    def _quick_revocation_check(self):
        """
        Lightweight revocation check: only is_blocked / is_active DB fields,
        with no cryptographic operations.

        Runs on EVERY request inside the cache window — provides
        near-instant reaction to server-side revocation instead of waiting
        for the full TTL to expire.

        Returns:
            tuple: (revoked: bool, reason: str | None)
        """
        try:
            from app_conf.models import SecureLicense
            row = (
                SecureLicense.objects
                .filter(is_active=True)
                .values('is_blocked', 'block_reason')
                .order_by('-id')
                .first()
            )
            if not row:
                return True, _("No active license found")
            if row['is_blocked']:
                reason = (row.get('block_reason') or '').strip()
                msg = _("License is blocked by server")
                return True, f"{msg}: {reason}" if reason else msg
            return False, None
        except Exception as e:
            logger.warning(f"Quick revocation check failed: {e}")
            # We do not block on an error - a full check will handle it in the next cycle
            return False, None

    def _validate_license_cached(self, request):
        """
        Validation with caching.

        TTL is read from LICENSE_CHECK_INTERVAL (default 60 s).
        Inside the cache window each request performs a lightweight DB
        revocation check (is_blocked / is_active) — server-side revocation
        is detected on the very next request without waiting for TTL expiry.
        """
        now = timezone.now()
        cache_ttl = self._get_cache_ttl()

        if (self._last_check and
                now - self._last_check < cache_ttl and
                self._validation_cache.get('valid')):
            # Easy revocation check - no crypto, just DB field
            revoked, revoke_msg = self._quick_revocation_check()
            if revoked:
                logger.warning(f"Quick revocation check triggered: {revoke_msg}")
                self._validation_cache = {
                    'valid': False,
                    'error': revoke_msg,
                    'reason_code': 'BLOCKED_BY_SERVER',
                }
                self._last_check = now
                return False, revoke_msg
            return True, None

        # Full cryptographic verification
        is_valid, error, reason_code = self._validate_license_full(request)

        self._validation_cache = {'valid': is_valid, 'error': error, 'reason_code': reason_code}
        self._last_check = now

        return is_valid, error
    
    def _verify_settings_compiled(self):
        """
        Verify that settings is loaded from compiled .so when one exists.
        Individual hash verification is handled by the RSA-signed code manifest.
        """
        try:
            import sys
            import os

            if 'SecBoard.settings' not in sys.modules:
                return

            settings_module = sys.modules['SecBoard.settings']
            settings_file = getattr(settings_module, '__file__', None)

            if not settings_file:
                return

            settings_dir = os.path.dirname(os.path.abspath(settings_file))

            settings_so_files = []
            if os.path.exists(settings_dir):
                for file in os.listdir(settings_dir):
                    if file.startswith('settings.cpython-') and file.endswith('.so'):
                        settings_so_files.append(file)

            if settings_file.endswith('.py') and settings_so_files:
                error_msg = (
                    f"SECURITY ALERT: Settings loaded from .py file, but .so file exists! "
                    f"Possible tampering: settings.so was replaced with settings.py. "
                    f"Found .so files: {settings_so_files}"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"Settings verification error: {str(e)}")
    
    def _verify_url_routing_integrity(self):
        """
        Verify that critical URL routing and middleware configuration is intact.
        Detects tampering with urls.py or MIDDLEWARE list at runtime.
        """
        try:
            from django.conf import settings as django_settings
            import sys
            
            middleware_list = getattr(django_settings, 'MIDDLEWARE', [])
            my_class = 'app_conf.license_middleware.SecureLicenseMiddleware'
            
            if my_class not in middleware_list:
                logger.critical("SECURITY: SecureLicenseMiddleware removed from MIDDLEWARE at runtime!")
                raise RuntimeError("License middleware integrity violation")
            
            # Verify license_crypto module is loaded from .so if .so exists
            if 'app_conf.license_crypto' in sys.modules:
                crypto_mod = sys.modules['app_conf.license_crypto']
                crypto_file = getattr(crypto_mod, '__file__', '') or ''
                crypto_dir = os.path.dirname(os.path.abspath(crypto_file)) if crypto_file else ''
                
                if crypto_dir:
                    has_crypto_so = any(
                        f.startswith('license_crypto.cpython-') and f.endswith('.so')
                        for f in os.listdir(crypto_dir)
                    ) if os.path.isdir(crypto_dir) else False
                    
                    if has_crypto_so and crypto_file.endswith('.py'):
                        logger.critical(
                            "SECURITY: license_crypto loaded from .py but .so exists! "
                            "Possible key replacement attack."
                        )
                        raise RuntimeError("License crypto module integrity violation")
            
            # Verify hardware_binding module integrity
            if 'app_conf.hardware_binding' in sys.modules:
                hw_mod = sys.modules['app_conf.hardware_binding']
                hw_file = getattr(hw_mod, '__file__', '') or ''
                hw_dir = os.path.dirname(os.path.abspath(hw_file)) if hw_file else ''
                
                if hw_dir:
                    has_hw_so = any(
                        f.startswith('hardware_binding.cpython-') and f.endswith('.so')
                        for f in os.listdir(hw_dir)
                    ) if os.path.isdir(hw_dir) else False
                    
                    if has_hw_so and hw_file.endswith('.py'):
                        logger.critical(
                            "SECURITY: hardware_binding loaded from .py but .so exists! "
                            "Possible Server ID spoofing attack."
                        )
                        raise RuntimeError("Hardware binding module integrity violation")
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"URL routing integrity check error: {str(e)}")
    
    _code_manifest_verified = False

    @staticmethod
    def _is_compiled_build():
        """Detect whether this is a compiled build (any .cpython-*.so present)."""
        from django.conf import settings as django_settings
        base_dir = str(getattr(django_settings, 'BASE_DIR', ''))
        if not base_dir:
            return False
        for _root, _dirs, _files in os.walk(base_dir):
            _dirs[:] = [d for d in _dirs if d not in ('venv', '.venv', '__pycache__', '.git')]
            if any(f.endswith('.so') and 'cpython' in f for f in _files):
                return True
        return False

    def _verify_code_manifest(self):
        """
        Verify RSA-signed code manifest: checks that every .so file in the
        build matches the hash recorded in .secboard_code_manifest.json and
        that the manifest itself is signed with the trusted RSA key.

        In compiled builds: every step is MANDATORY — any failure is fatal.
        In development builds (no .so files): silently skipped.
        """
        if SecureLicenseMiddleware._code_manifest_verified:
            return

        from django.conf import settings as django_settings
        base_dir = str(getattr(django_settings, 'BASE_DIR', ''))
        if not base_dir:
            return

        _is_compiled = self._is_compiled_build()

        manifest_path = os.path.join(base_dir, '.secboard_code_manifest.json')

        if not os.path.exists(manifest_path):
            if _is_compiled:
                logger.critical("SECURITY: Compiled .so files present but code manifest is MISSING!")
                raise RuntimeError(
                    "Code manifest (.secboard_code_manifest.json) not found in compiled build — "
                    "possible tampering (manifest deleted to bypass integrity checks)"
                )
            SecureLicenseMiddleware._code_manifest_verified = True
            return

        if not _is_compiled:
            SecureLicenseMiddleware._code_manifest_verified = True
            return

        # From here, _is_compiled is True and manifest exists.
        # Every failure is FATAL — no silent fallbacks.
        try:
            import json as _json
            import hashlib
            import base64

            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = _json.load(f)

            signature_b64 = manifest.get('signature', '')
            files = manifest.get('files', {})

            if not signature_b64 or not files:
                logger.critical("SECURITY: Code manifest exists but has no signature or files!")
                raise RuntimeError("Code manifest is unsigned or empty in compiled build — possible tampering")

            from app_conf.license_crypto import LicenseCrypto
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
            from cryptography.hazmat.backends import default_backend
            import hmac as _hmac_mod

            public_key_pem = LicenseCrypto._get_public_key_pem()

            # ── Cross-module key-hash pin ─────────────────────────────────────
            # Verify the loaded public key matches the fingerprint embedded at
            # build time in THIS module (license_middleware).  An attacker who
            # replaces license_crypto.so must ALSO rebuild license_middleware.so
            # (which is itself listed in the manifest), making the attack require
            # modifying and recompiling two interdependent binaries plus
            # re-signing the manifest — significantly raising the bar.
            _pem_bytes = (
                public_key_pem if isinstance(public_key_pem, bytes)
                else public_key_pem.encode('utf-8')
            )
            _actual_key_hash = hashlib.sha256(_pem_bytes).hexdigest()

            if _EXPECTED_CRYPTO_KEY_HASH:
                if not _hmac_mod.compare_digest(_actual_key_hash, _EXPECTED_CRYPTO_KEY_HASH):
                    logger.critical(
                        "SECURITY: RSA public key fingerprint mismatch — "
                        "license_crypto.so replaced with a different key! "
                        f"expected={_EXPECTED_CRYPTO_KEY_HASH[:16]}... "
                        f"actual={_actual_key_hash[:16]}..."
                    )
                    raise RuntimeError(
                        "RSA public key fingerprint mismatch — "
                        "license_crypto module integrity violation"
                    )
            else:
                # _EXPECTED_CRYPTO_KEY_HASH must be populated in compiled builds
                # (injected by build pipeline Step 2.5b).  An empty value in a
                # compiled build means the pipeline was skipped — refuse to start.
                if _is_compiled:
                    logger.critical(
                        "SECURITY: _EXPECTED_CRYPTO_KEY_HASH is empty in a compiled build — "
                        "build pipeline did not inject the RSA key fingerprint (Step 2.5b). "
                        f"Current key hash={_actual_key_hash[:16]}... — refusing to proceed."
                    )
                    raise RuntimeError(
                        "_EXPECTED_CRYPTO_KEY_HASH not set in compiled build — "
                        "RSA key fingerprint injection was skipped during build"
                    )
                logger.debug(
                    f"Dev build: RSA key loaded ok, hash={_actual_key_hash[:16]}... "
                    "(cross-module pin check skipped — _EXPECTED_CRYPTO_KEY_HASH empty)"
                )
            # ─────────────────────────────────────────────────────────────────

            public_key = serialization.load_pem_public_key(
                _pem_bytes,
                backend=default_backend()
            )

            canonical = _json.dumps(files, sort_keys=True, separators=(',', ':'))
            signature_bytes = base64.b64decode(signature_b64)

            try:
                public_key.verify(
                    signature_bytes,
                    canonical.encode('utf-8'),
                    asym_padding.PSS(
                        mgf=asym_padding.MGF1(hashes.SHA256()),
                        salt_length=asym_padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            except Exception:
                logger.critical("SECURITY: Code manifest RSA signature INVALID — build has been tampered with!")
                raise RuntimeError("Code manifest signature verification failed")

            for rel_path, expected_hash in files.items():
                full_path = os.path.join(base_dir, rel_path)
                if not os.path.exists(full_path):
                    logger.critical(f"SECURITY: .so file missing from build: {rel_path}")
                    raise RuntimeError(f"Code manifest: missing .so file {rel_path}")
                hasher = hashlib.sha256()
                with open(full_path, 'rb') as fh:
                    for chunk in iter(lambda: fh.read(8192), b''):
                        hasher.update(chunk)
                if hasher.hexdigest() != expected_hash:
                    logger.critical(f"SECURITY: .so file hash mismatch: {rel_path}")
                    raise RuntimeError(f"Code manifest: .so file tampered — {rel_path}")

            logger.info(f"Code manifest verified: {len(files)} .so files, RSA signature valid")
            SecureLicenseMiddleware._code_manifest_verified = True

        except RuntimeError:
            raise
        except Exception as e:
            # In compiled builds, ANY verification error is fatal — no silent bypass.
            logger.critical(f"SECURITY: Code manifest verification failed with unexpected error: {str(e)}")
            raise RuntimeError(f"Code manifest verification failed: {str(e)}")

    def _validate_license_full(self, request):
        """Full multi-level validation"""
        try:
            # Verification of RSA-signature code manifest (.so files)
            self._verify_code_manifest()

            # Checking that settings is loaded from .so (if .so exists)
            self._verify_settings_compiled()
            
            # Checking the integrity of URL routing and critical modules
            self._verify_url_routing_integrity()
            
            from app_conf.models import SecureLicense
            from app_conf.license_manager import LicenseValidator
            from app_conf.hardware_binding import HardwareFingerprint
            from django.contrib.auth.models import User
            
            # 1. License check (search all to check blocking)
            license_obj = SecureLicense.objects.order_by('-id').first()
            if not license_obj:
                return False, _("No license found"), 'NO_LICENSE'
            
            # 1.5. Checking remote lock from server (FIRST to take priority)
            if hasattr(license_obj, 'is_blocked') and license_obj.is_blocked:
                block_reason = getattr(license_obj, 'block_reason', '')
                error_msg = _("License is blocked by server")
                if block_reason:
                    error_msg += f": {block_reason}"
                return False, error_msg, 'BLOCKED_BY_SERVER'
            
            # 1.6. Is_active check (after blocking check)
            if not license_obj.is_active:
                return False, _("License is not active"), 'NOT_ACTIVE'

            # 1.7. Source policy: server may disable verification for this deployment.
            license_data_meta = license_obj.encrypted_data or {}
            if license_data_meta.get('verification_enforced') is False:
                logger.debug(
                    "License verification relaxed by server source policy (verification_enforced=False)"
                )
                return True, None, None
            
            # 2. Verification of signature and integrity
            license_data = license_obj.get_license_data()
            if not license_data:
                return False, _("License signature verification failed"), 'SIGNATURE_FAILED'
            
            # 3. Checking the expiration date
            if not license_obj.is_valid():
                return False, _("License has expired"), 'EXPIRED'
            
            # 4. Checking Server ID (hash of Hardware ID + HTTP_HOST)
            current_server_id = HardwareFingerprint.get_server_id().strip()
            stored_server_id = (license_obj.hardware_fingerprint or '').strip()
            
            logger.info(f"Server ID validation: stored={stored_server_id[:16] if stored_server_id else 'N/A'}... (length: {len(stored_server_id)}), current={current_server_id[:16]}... (length: {len(current_server_id)})")
            
            if stored_server_id != current_server_id:
                logger.critical(
                    f"Server ID mismatch! "
                    f"License Server ID: {stored_server_id[:16] if stored_server_id else 'N/A'}... (length: {len(stored_server_id)}), "
                    f"Current Server ID: {current_server_id[:16]}... (length: {len(current_server_id)}) "
                    f"Possible license cloning attempt or Server ID changed after restart."
                )
                return False, _("License Server ID binding validation failed"), 'HARDWARE_MISMATCH'

            # 4.5. Extended hardware report verification
            # Pass license_key_hash so the HMAC is bound to the active licence —
            # forging the report now requires both filesystem AND database access.
            # allow_create=True: if the report file is missing (e.g. first deploy,
            # container restart without persistent volume) the baseline is
            # auto-created rather than hard-failing.  Security is maintained by
            # the HMAC binding to license_key_hash — recreating the file silently
            # requires both filesystem write access AND knowledge of license_key_hash
            # (from the database), which is equivalent to full system compromise.
            hw_report = HardwareFingerprint.verify_hardware_report(
                tolerance=2,
                license_key_hash=license_obj.license_key_hash or '',
                allow_create=True,
            )
            if not hw_report['valid']:
                if hw_report.get('missing_report'):
                    # Critical log is already emitted inside verify_hardware_report().
                    pass
                elif not hw_report['report_intact']:
                    logger.critical("SECURITY: Hardware report file tampered with — HMAC invalid")
                else:
                    logger.critical(
                        f"SECURITY: Hardware drift beyond tolerance — "
                        f"{hw_report['drift_count']} components changed: {', '.join(hw_report['changed'])}"
                    )
                return False, _("Hardware integrity verification failed"), 'HARDWARE_REPORT_INVALID'
            
            # 5. Checking the user limit
            active_users = User.objects.filter(is_active=True).count()
            max_users = license_obj.get_user_limit()
            if active_users > max_users:
                return False, _("User limit exceeded"), 'USER_LIMIT_EXCEEDED'
            
            # 6. Checking the connection with the server (if there is no offline period)
            if not self._check_license_server_heartbeat(license_obj):
                return False, _("License server validation failed"), 'SERVER_FAILED'
            
            return True, None, None
            
        except Exception as e:
            logger.error(f"License validation error: {str(e)}")
            return False, _("License validation error"), 'VALIDATION_ERROR'
    
    def _check_license_server_heartbeat(self, license_obj):
        """
        Server connectivity check with heartbeat.
        Flow: attempt heartbeat → on failure fall back to grace period.
        """
        from app_conf.license_server_api import OfflineGracePeriodManager

        last_heartbeat = license_obj.heartbeats.order_by('-timestamp').first()
        heartbeat_interval = timedelta(hours=1)
        needs_heartbeat = (
            not last_heartbeat
            or (timezone.now() - last_heartbeat.timestamp > heartbeat_interval)
        )

        if not needs_heartbeat:
            return True

        success = self._send_heartbeat(license_obj)

        if success:
            OfflineGracePeriodManager.clear_grace_period(license_obj)
            return True

        # Heartbeat failed — server unreachable or rejected.
        grace_valid, grace_msg = OfflineGracePeriodManager.check_grace_period(license_obj)
        if grace_valid:
            logger.warning(f"Heartbeat failed, using grace period: {grace_msg}")
            return True

        # No active grace period — start one (first failure) or reject (expired).
        if not license_obj.offline_until:
            OfflineGracePeriodManager.start_grace_period(license_obj)
            logger.warning("Heartbeat failed, started new offline grace period")
            return True

        # Grace period was set but has expired.
        logger.error(f"Heartbeat failed and grace period expired: {grace_msg}")
        return False
    
    def _send_heartbeat(self, license_obj):
        """Send heartbeat to license server"""
        try:
            from app_conf.license_server_api import LicenseServerAPI
            from app_conf.models import LicenseHeartbeat
            
            # Collection of statistics
            usage_stats = self._collect_usage_stats()
            
            # Sending to the server
            success, response_data = LicenseServerAPI.send_heartbeat(
                license_obj.license_key,
                usage_stats
            )
            
            # Processing the response from the server and synchronizing the lock status
            error_message = ''
            update_fields = []
            
            if response_data:
                # Synchronize lock status from server
                server_is_blocked = response_data.get('is_blocked', False)
                server_block_reason = response_data.get('block_reason', '') or ''
                
                # Make sure block_reason is always a string (not None)
                if server_block_reason is None:
                    server_block_reason = ''
                
                # Update local lock status
                if hasattr(license_obj, 'is_blocked'):
                    if license_obj.is_blocked != server_is_blocked:
                        license_obj.is_blocked = server_is_blocked
                        update_fields.append('is_blocked')
                        if server_is_blocked:
                            logger.critical(f"License blocked by server! Reason: {server_block_reason}")
                        else:
                            logger.info("License unblocked by server")
                    
                    if license_obj.block_reason != server_block_reason:
                        license_obj.block_reason = server_block_reason
                        update_fields.append('block_reason')
                
                verification_enforced = response_data.get('verification_enforced')
                if verification_enforced is not None:
                    meta = dict(license_obj.encrypted_data or {})
                    if meta.get('verification_enforced') != bool(verification_enforced):
                        meta['verification_enforced'] = bool(verification_enforced)
                        license_obj.encrypted_data = meta
                        update_fields.append('encrypted_data')

                # If the license is blocked on the server, deactivate locally
                if server_is_blocked:
                    if license_obj.is_active:
                        license_obj.is_active = False
                        update_fields.append('is_active')
                    error_message = f"License is blocked: {server_block_reason}" if server_block_reason else "License is blocked"
                
                # Check if the server returned a concurrent use error
                if response_data.get('status') == 'error':
                    error_message = response_data.get('message', 'Unknown error')
                    # If the license is blocked due to concurrent use
                    if 'concurrent' in error_message.lower() or ('blocked' in error_message.lower() and not server_is_blocked):
                        logger.critical(
                            f"License blocked due to concurrent usage! "
                            f"Message: {error_message}"
                        )
                        # Deactivate the license locally
                        if license_obj.is_active:
                            license_obj.is_active = False
                            update_fields.append('is_active')
                        if hasattr(license_obj, 'is_blocked'):
                            license_obj.is_blocked = True
                            update_fields.append('is_blocked')
                        if hasattr(license_obj, 'block_reason'):
                            license_obj.block_reason = error_message or ''
                            update_fields.append('block_reason')
                elif not response_data.get('license_valid', True):
                    error_message = 'License is no longer valid on server'
                    if license_obj.is_active:
                        license_obj.is_active = False
                        update_fields.append('is_active')
            
            # Save changes if any
            if update_fields:
                license_obj.save(update_fields=update_fields)
            
            # Logging in
            LicenseHeartbeat.objects.create(
                license=license_obj,
                response_code=200 if success and not error_message else 0,
                response_data=response_data,
                usage_stats=usage_stats,
                success=success and not error_message,
                error_message=error_message if error_message else ('' if success else 'Connection failed')
            )
            
            return success and not error_message
            
        except Exception as e:
            logger.warning(f"Heartbeat failed: {str(e)}")
            return False
    
    def _collect_usage_stats(self):
        """Collect usage statistics for sending to the server"""
        from django.contrib.auth.models import User
        from app_conf.models import Company
        
        return {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'companies': Company.objects.count(),
            'timestamp': str(timezone.now()),
        }
    
    def _get_current_license(self):
        """Get the current license"""
        from app_conf.models import SecureLicense
        return SecureLicense.objects.filter(is_active=True).first()
    
    def _get_error_details(self, request, error_msg):
        """Get detailed error information for display"""
        from app_conf.hardware_binding import HardwareFingerprint
        from app_conf.models import SecureLicense
        from django.contrib.auth.models import User
        
        # We always get Server ID (hash of Hardware ID + HTTP_HOST)
        server_id = HardwareFingerprint.get_server_id()
        hardware_info = HardwareFingerprint.get_fingerprint_info()
        
        details = {
            'reason_code': self._validation_cache.get('reason_code', 'UNKNOWN'),
            'hardware_id': server_id,  # On the server this is stored as hardware_id, but it is now the Server ID
            'hardware_info': hardware_info,
        }
        
        # We add information about the license, if there is one
        license_obj = SecureLicense.objects.filter(is_active=True).first()
        if license_obj:
            try:
                license_data = license_obj.get_license_data()
                if license_data:
                    details['max_users'] = license_data.get('max_users', 0)
                    details['active_users'] = User.objects.filter(is_active=True).count()
                    details['expiration_date'] = license_data.get('expiration_date', '')
            except:
                pass
        else:
            # If there is no license, we still show the number of users
            details['active_users'] = User.objects.filter(is_active=True).count()
        
        return details
    
    # Module access check disabled
    # def _check_module_access_by_url(self, request, license_obj):
    #     """
    # URL-based module access validation
    #     
    #     Args:
    #         request: HTTP request object
    # license_obj: SecureLicense object
    #         
    #     Returns:
    # str: Error message if access is denied, None if allowed
    #     """
    #     try:
    #         from app_conf.license_manager import ModuleAccessController
    #         
    # # Mapping URL prefixes to module keys
    #         url_module_mapping = {
    #             'app_risk': 'risk',
    #             'app_compliance': 'compliance',
    #             'app_gdpr': 'gdpr',
    #             'app_gophish': 'gophish',
    #             'app_tprm': 'tprm',
    #             'app_incident': 'incident',
    #             'app_asset': 'asset',
    #         }
    #         
    # # We get the path without the language prefix (if any)
    #         path = request.path.strip('/')
    # # Remove the language prefix (uk/, en/, ru/) if it is present
    #         path_parts = path.split('/', 1)
    #         if len(path_parts) > 1 and path_parts[0] in ['uk', 'en', 'ru']:
    #             path = path_parts[1]
    #         
    # # We check whether the URL starts with the module prefix
    #         for url_prefix, module_key in url_module_mapping.items():
    #             if path.startswith(url_prefix + '/') or path == url_prefix:
    # # We check access to the module
    #                 has_access = ModuleAccessController.check_access(license_obj, module_key)
    #                 
    #                 if not has_access:
    #                     module_info = ModuleAccessController.AVAILABLE_MODULES.get(module_key, {})
    #                     module_display_name = module_info.get('name_uk', module_info.get('name', module_key))
    #                     
    #                     logger.warning(
    #                         f"Module access denied: User attempted to access '{module_key}' module "
    #                         f"(URL: {request.path}) but license does not include this module"
    #                     )
    #                     
    #                     return _(
    #                         "Your license does not include access to module: {module_name}. "
    #                         "Please contact support to upgrade your license."
    #                     ).format(module_name=module_display_name)
    #         
    #         return None
    #         
    #     except Exception as e:
    #         logger.error(f"Error checking module access by URL: {str(e)}")
    # # In the event of an error, we do not block access so as not to disrupt the system
    #         return None

