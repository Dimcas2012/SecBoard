# SecBoard\app_conf\license_server_api.py
"""
License Server API Client
"""

import os
import requests
import logging
import socket
import platform
import hashlib
import hmac as _hmac
import json as _json
import base64 as _base64
import uuid
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .hardware_binding import HardwareFingerprint

logger = logging.getLogger(__name__)

_last_challenge_nonce = None


def _heartbeat_lock_key(license_key):
    """Stable lock key per license to prevent concurrent heartbeats."""
    key_hash = hashlib.sha256((license_key or '').encode('utf-8')).hexdigest()
    return f"license_heartbeat_lock:{key_hash}"


def _acquire_heartbeat_lock(license_key):
    """
    Acquire distributed lock for a specific license heartbeat.

    Uses Django cache `add` for atomic set-if-not-exists (works with Redis cache).
    Returns (acquired: bool, token: str, lock_key: str).
    """
    lock_key = _heartbeat_lock_key(license_key)
    token = uuid.uuid4().hex
    lock_ttl = int(getattr(settings, 'LICENSE_HEARTBEAT_LOCK_TTL', 30))
    acquired = cache.add(lock_key, token, timeout=lock_ttl)
    return acquired, token, lock_key


def _release_heartbeat_lock(lock_key, token):
    """Release lock only if this process still owns it."""
    try:
        current = cache.get(lock_key)
        if current == token:
            cache.delete(lock_key)
    except Exception as e:
        logger.warning(f"Failed to release heartbeat lock {lock_key}: {e}")


def _verify_server_response_signature(data):
    """
    Verify the RSA-PSS-SHA256 signature attached to every license server response.

    The server signs the full payload dict (minus the response_signature field
    itself) with the RSA private key that is also used to sign license keys.
    We verify using the public key embedded in license_crypto.py — the only
    trusted copy of the key on the client side.

    Returns:
        (True,  None)      — signature is present and valid
        (False, reason)    — signature missing or invalid (MITM / rogue server)
    """
    from cryptography.hazmat.primitives.asymmetric import padding as _pad
    from cryptography.hazmat.primitives import hashes as _hashes, serialization as _ser
    from cryptography.hazmat.backends import default_backend as _be
    from cryptography.exceptions import InvalidSignature

    sig_b64 = data.get('response_signature', '')
    if not sig_b64:
        return False, "response_signature field missing — unsigned response"

    # Reconstruct the dict that was signed (everything EXCEPT response_signature).
    signed_data = {k: v for k, v in data.items() if k != 'response_signature'}

    try:
        # Canonical serialisation — must match RSAManager.serialize_data()
        canonical = _json.dumps(signed_data, sort_keys=True, separators=(',', ':')).encode('utf-8')

        sig_clean = sig_b64.strip()
        pad = len(sig_clean) % 4
        if pad:
            sig_clean += '=' * (4 - pad)
        sig_bytes = _base64.b64decode(sig_clean, validate=True)

        from app_conf.license_crypto import LicenseCrypto
        public_key = _ser.load_pem_public_key(
            LicenseCrypto._get_public_key_pem(),
            backend=_be()
        )
        public_key.verify(
            sig_bytes,
            canonical,
            _pad.PSS(
                mgf=_pad.MGF1(_hashes.SHA256()),
                salt_length=_pad.PSS.MAX_LENGTH
            ),
            _hashes.SHA256()
        )
        return True, None
    except InvalidSignature:
        return (
            False,
            "RSA-PSS verification failed — possible MITM attack or rogue license server"
        )
    except Exception as _e:
        return False, f"Signature verification error: {_e}"


def _nonce_file_path():
    base_dir = getattr(settings, 'BASE_DIR', '')
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return Path(base_dir) / '.secboard_challenge_nonce'


def _compute_challenge_response(nonce, hardware_id, license_key):
    """Compute HMAC response for server challenge nonce."""
    license_key_hash = hashlib.sha256(license_key.encode()).hexdigest()
    key = hashlib.sha256(f"{hardware_id}:{license_key_hash}".encode()).digest()
    return _hmac.new(key, nonce.encode(), hashlib.sha256).hexdigest()


def _nonce_hmac_key():
    """Derive a key for protecting the on-disk nonce file from SECRET_KEY."""
    try:
        from django.conf import settings as _s
        _secret = (_s.SECRET_KEY or '').encode('utf-8')
    except Exception:
        _secret = b''
    return hashlib.sha256(b'nonce_file_integrity:' + _secret).digest()


def _store_challenge_nonce(nonce):
    """
    Persist nonce to memory AND disk so it survives process restarts.

    The on-disk copy is stored as JSON with an HMAC-SHA256 MAC derived from
    Django's SECRET_KEY.  This prevents an attacker who has filesystem write
    access from injecting a custom nonce to influence the challenge-response
    sent to the license server.
    """
    global _last_challenge_nonce
    _last_challenge_nonce = nonce
    try:
        p = _nonce_file_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        _mac = _hmac.new(
            _nonce_hmac_key(),
            nonce.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        p.write_text(_json.dumps({'nonce': nonce, 'mac': _mac}), encoding='utf-8')
        p.chmod(0o600)
    except Exception as e:
        logger.warning(f"Could not persist challenge nonce to disk: {e}")


def _get_and_clear_challenge_nonce():
    """
    Get the stored challenge nonce (memory first, then disk), verify its
    integrity HMAC, clear it, and return the value.

    If the on-disk HMAC does not match (file was tampered with), the nonce
    is discarded and a CRITICAL security event is logged.  Legacy plain-text
    nonce files (written before this protection was added) are accepted with
    a WARNING and upgraded on next write.
    """
    global _last_challenge_nonce
    nonce = _last_challenge_nonce
    if not nonce:
        try:
            p = _nonce_file_path()
            if p.exists():
                raw = p.read_text(encoding='utf-8').strip()
                try:
                    obj = _json.loads(raw)
                    stored_nonce = obj.get('nonce', '')
                    stored_mac = obj.get('mac', '')
                    expected_mac = _hmac.new(
                        _nonce_hmac_key(),
                        stored_nonce.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    if _hmac.compare_digest(stored_mac, expected_mac):
                        nonce = stored_nonce
                    else:
                        logger.critical(
                            "SECURITY: Challenge nonce file HMAC mismatch — "
                            "possible tampering with .secboard_challenge_nonce. "
                            "Nonce discarded; next heartbeat will be sent without "
                            "challenge-response."
                        )
                        nonce = None
                except (_json.JSONDecodeError, AttributeError):
                    # Legacy format: plain-text nonce without MAC.
                    # Accept with a warning; file will be upgraded on next write.
                    nonce = raw if raw else None
                    if nonce:
                        logger.warning(
                            "Challenge nonce file is in legacy format (no HMAC). "
                            "Accepted this time; will be upgraded on next store."
                        )
        except Exception as e:
            logger.warning(f"Could not read challenge nonce from disk: {e}")
    _last_challenge_nonce = None
    try:
        p = _nonce_file_path()
        if p.exists():
            p.unlink()
    except Exception:
        pass
    return nonce


class LicenseServerAPI:
    """
    API client for communication with the central license server.

    This class is responsible for:
    - Online license validation
    - Sending heartbeat messages
    - Sending usage statistics
    - Checking license status
    """
    
    # License server URL (must be configured in settings.py)
    # LICENSE_SERVER_URL = "https://license.secboard.online/api/v1/"
    
    @classmethod
    def _get_server_url(cls):
        """Get license server URL from settings"""
        return getattr(settings, 'LICENSE_SERVER_URL', 'https://license.secboard.online/api/v1/')
    
    @classmethod
    def _get_timeout(cls):
        """Get request timeout"""
        return getattr(settings, 'LICENSE_SERVER_TIMEOUT', 10)
    
    @classmethod
    def validate_online(cls, license_key):
        """
        Online license validation on the central server.
        Checks both license validity and block status.

        Args:
            license_key (str): License key

        Returns:
            tuple: (is_valid: bool or None, data: dict or None)
                  None if the server is unreachable (offline mode)
        """
        try:
            # We use the new endpoint /api/v1/licenses/validate/
            base_url = cls._get_server_url()
            server_url = cls._try_server_urls('ping/')  # Find a working URL
            if not server_url:
                logger.warning("License server unreachable (no working URL found)")
                return None, None
            
            url = f"{server_url}licenses/validate/"
            
            # Get Server ID (hash from Hardware ID + HTTP_HOST)
            server_id = HardwareFingerprint.get_server_id()
            
            # Get additional information about the system
            components = HardwareFingerprint.get_hardware_components(include_server_id=True)
            
            # Preparation of request data
            payload = {
                'license_key': license_key,
                'hardware_id': server_id,  # We use Server ID instead of Hardware ID
                'platform_version': '',
            }
            
            # Sending a request
            logger.info(f"Sending validation request to license server: {url}")
            verify_ssl = not ('10.1.10.11' in url or '127.0.0.1' in url or url.startswith('http://'))
            headers = {'Content-Type': 'application/json'}
            if '10.1.10.11' in url:
                headers['Host'] = 'license.secboard.online'
            
            response = requests.post(
                url,
                json=payload,
                timeout=cls._get_timeout(),
                headers=headers,
                verify=verify_ssl
            )
            
            # Response processing
            if response.status_code == 200:
                data = response.json()

                # Verify server response signature BEFORE trusting the data.
                # An unsigned or invalidly-signed response indicates a possible
                # MITM attack or a rogue license server — treat as unreachable.
                _sig_ok, _sig_err = _verify_server_response_signature(data)
                if not _sig_ok:
                    logger.critical(
                        f"SECURITY: License validation response signature invalid: "
                        f"{_sig_err}. Treating as server unreachable to avoid "
                        "accepting data from a rogue/MITM server."
                    )
                    return None, None

                logger.info(f"Received verified 200 response from server: {data}")
                is_valid = data.get('valid', False)
                is_blocked = data.get('is_blocked', False)
                block_reason = data.get('block_reason', '')
                
                logger.info(f"Parsed 200 response: is_valid={is_valid}, is_blocked={is_blocked}, block_reason={block_reason}")
                
                # If the license is blocked, we consider it invalid
                if is_blocked:
                    error_msg = f"License is blocked: {block_reason}" if block_reason else "License is blocked"
                    logger.warning(f"License validation failed (BLOCKED in 200 response): {error_msg}")
                    return False, {'error': error_msg, 'is_blocked': True, 'block_reason': block_reason, 'valid': False}
                
                # If valid: false (even if not blocked), return False
                if not is_valid:
                    error_msg = data.get('error', 'License validation failed on server')
                    logger.warning(f"License validation failed (valid=False in 200 response): {error_msg}")
                    return False, {'error': error_msg, 'is_blocked': False, 'valid': False}
                
                # Capture initial challenge nonce from server.
                # Only store it AFTER signature verification above.
                seed_nonce = data.get('challenge_nonce')
                if seed_nonce:
                    _store_challenge_nonce(seed_nonce)
                    logger.info("Stored initial challenge nonce from verified validation response")

                logger.info(f"License validation response: VALID")
                return True, data
            
            elif response.status_code == 404:
                logger.warning("License not found on server")
                # If the license is not found on the server, we consider it blocked
                return False, {'error': 'License not found', 'is_blocked': True, 'block_reason': 'License not found on server'}
            
            elif response.status_code == 403:
                # May be blocked or invalid
                try:
                    data = response.json()
                    logger.info(f"Received 403 response from server: {data}")
                    is_blocked = data.get('is_blocked', False)
                    block_reason = data.get('block_reason', '')
                    error_msg = data.get('error', 'License revoked or suspended')
                    
                    logger.info(f"Parsed 403 response: is_blocked={is_blocked}, block_reason={block_reason}, error={error_msg}")
                    
                    if is_blocked:
                        error_msg = f"License is blocked: {block_reason}" if block_reason else "License is blocked"
                        logger.warning(f"License validation failed (BLOCKED): {error_msg}")
                        return False, {'error': error_msg, 'is_blocked': True, 'block_reason': block_reason, 'valid': False}
                    else:
                        logger.warning(f"License validation failed (NOT BLOCKED): {error_msg}")
                        return False, {'error': error_msg, 'is_blocked': False, 'valid': False}
                except Exception as e:
                    logger.error(f"License revoked or suspended (could not parse response: {str(e)})")
                    logger.error(f"Response content: {response.text[:500]}")
                    return False, {'error': 'License revoked or suspended', 'valid': False}
            
            else:
                logger.error(f"License server returned status {response.status_code}")
                return None, None
            
        except requests.ConnectionError as e:
            logger.warning(f"License server unreachable (offline mode): {str(e)}")
            return None, None
        
        except requests.Timeout as e:
            logger.warning(f"License server timeout (offline mode): {str(e)}")
            return None, None
        
        except Exception as e:
            logger.error(f"License validation error: {str(e)}")
            return None, None
    
    @classmethod
    def _get_actual_server_url(cls):
        """Get actual license server URL (with internal IP support)"""
        base_url = cls._get_server_url()
        
        # If the server is not accessible via the public URL, try via the internal IP
        # Both servers on the same Proxmox (10.1.10.11)
        try:
            import socket
            import subprocess
            
            # Get the internal IP of the current server
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                local_ips = [ip.strip() for ip in result.stdout.strip().split() if ip.strip()]
                # If there is IP 10.1.10.11, use it
                if '10.1.10.11' in local_ips:
                    # Replace the domain with an internal IP
                    if 'license.secboard.online' in base_url:
                        internal_url = base_url.replace('license.secboard.online', '10.1.10.11')
                        # Check the availability of the internal URL
                        test_url = internal_url.replace('/api/v1/', '')
                        try:
                            test_response = requests.get(f"{test_url}ping/", timeout=2, verify=False)
                            if test_response.status_code == 200:
                                logger.info(f"Using internal IP for license server: {internal_url}")
                                return internal_url
                        except:
                            pass
        except:
            pass
        
        return base_url
    
    @classmethod
    def _try_server_urls(cls, endpoint='ping/'):
        """Try connecting to the server via different URLs"""
        base_url = cls._get_server_url()
        urls_to_try = []
        
        # Add different URL options to try
        try:
            import subprocess
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                local_ips = [ip.strip() for ip in result.stdout.strip().split() if ip.strip()]
                if '10.1.10.11' in local_ips:
                    # Both servers are on the same Proxmox, try via internal IP
                    # First, through direct access to the Gunicorn license server (port 9010)
                    urls_to_try.append('http://10.1.10.11:9010/api/v1/')
                    # Then via HTTP on the internal IP (via Nginx)
                    urls_to_try.append('http://10.1.10.11/api/v1/')
                    # Then via HTTPS on the internal IP (via Nginx)
                    urls_to_try.append('https://10.1.10.11/api/v1/')
        except:
            pass
        
        # Add the public URL at the end
        urls_to_try.append(base_url)
        
        # Try each URL
        for url in urls_to_try:
            try:
                test_url = f"{url}{endpoint}"
                verify_ssl = not ('127.0.0.1' in url or '10.1.10.11' in url or url.startswith('http://'))
                # Add Host header for internal IP (for virtual hosts)
                headers = {}
                if '10.1.10.11' in url:
                    headers['Host'] = 'license.secboard.online'
                response = requests.get(test_url, timeout=3, verify=verify_ssl, headers=headers)
                if response.status_code == 200:
                    logger.info(f"Found working license server URL: {url}")
                    return url
            except Exception as e:
                logger.debug(f"URL {url} failed: {str(e)}")
                continue
        
        # If all else fails, return the base URL
        logger.warning(f"Could not find working license server URL, using default: {base_url}")
        return base_url
    
    @classmethod
    def send_heartbeat(cls, license_key, usage_stats=None):
        """
        Send a heartbeat message to the license server.

        Args:
            license_key (str): License key
            usage_stats (dict): Usage statistics (optional)

        Returns:
            tuple: (success: bool, response_data: dict or None)
        """
        acquired, lock_token, lock_key = _acquire_heartbeat_lock(license_key)
        if not acquired:
            # Another process is already sending heartbeat for this license.
            # Return success-like response to avoid false offline/grace transitions.
            logger.info("Heartbeat skipped: another process is already sending it")
            return True, {
                'status': 'ok',
                'message': 'Heartbeat already in progress',
                'deduplicated': True,
            }

        try:
            # Try to find an available server URL
            base_url = cls._get_server_url()
            server_url = cls._try_server_urls('ping/')
            # Correct URL for heartbeat: /api/v1/licenses/heartbeat/
            url = f"{server_url}licenses/heartbeat/"
            logger.info(f"Using license server URL: {server_url}")
            
            # Preparation of statistics
            if usage_stats is None:
                usage_stats = cls._collect_usage_stats()
            
            # Get additional information about the system
            components = HardwareFingerprint.get_hardware_components(include_server_id=True)  # Include the server_id to send to the server
            
            # Get the number of users
            try:
                from django.contrib.auth.models import User
                active_users = User.objects.filter(is_active=True).count()
                total_users = User.objects.count()
            except Exception as e:
                logger.warning(f"Failed to get user counts: {str(e)}")
                active_users = usage_stats.get('users', {}).get('active', 0)
                total_users = usage_stats.get('users', {}).get('total', 0)
            
            # Get uptime (if available)
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.read().split()[0])
                    uptime_hours = int(uptime_seconds / 3600)
            except:
                uptime_hours = 0
            
            # Preparation of request data (according to the serializer on the server)
            # IMPORTANT: Use get_server_id() instead of generate_fingerprint()
            server_id = HardwareFingerprint.get_server_id()
            
            extra = {
                'hostname': components.get('hostname', socket.gethostname()),
                'fqdn': components.get('fqdn', socket.getfqdn()),
                'domain': components.get('domain', ''),
                'platform': platform.system(),
                'usage_stats': usage_stats,
            }
            
            # Challenge-response: include response to server's nonce
            pending_nonce = _get_and_clear_challenge_nonce()
            if pending_nonce:
                cr = _compute_challenge_response(pending_nonce, server_id, license_key)
                extra['challenge_nonce'] = pending_nonce
                extra['challenge_response'] = cr
            
            payload = {
                'license_key': license_key,
                'hardware_id': server_id,
                'active_users': active_users,
                'total_users': total_users,
                'platform_version': getattr(settings, 'VERSION', ''),
                'uptime_hours': uptime_hours,
                'extra_data': extra,
            }
            
            # Sending a request
            logger.info(f"Sending heartbeat to license server: {url} (Server ID: {server_id[:16]}...)")
            # Use verify=False for internal connections
            verify_ssl = not ('10.1.10.11' in url or '127.0.0.1' in url)
            # Add Host header for internal IP (for virtual hosts)
            headers = {'Content-Type': 'application/json'}
            if '10.1.10.11' in url:
                headers['Host'] = 'license.secboard.online'
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=cls._get_timeout(),
                    headers=headers,
                    verify=verify_ssl
                )
            except requests.ConnectionError as e:
                logger.error(f"Connection error to {url}: {str(e)}")
                # Try using the internal IP if you haven't tried yet
                if '10.1.10.11' not in url:
                    logger.info("Trying internal IP as fallback...")
                    internal_url = base_url.replace('license.secboard.online', '10.1.10.11')
                    url = f"{internal_url}licenses/heartbeat/"
                    headers_fallback = {'Content-Type': 'application/json', 'Host': 'license.secboard.online'}
                    try:
                        response = requests.post(
                            url,
                            json=payload,
                            timeout=cls._get_timeout(),
                            headers=headers_fallback,
                            verify=False
                        )
                        logger.info(f"Successfully connected via internal IP: {url}")
                    except Exception as e2:
                        logger.error(f"Failed to connect via internal IP: {str(e2)}")
                        raise e
                else:
                    raise
            
            # Response processing
            if response.status_code == 200:
                data = response.json()

                # Verify server response signature BEFORE trusting the data.
                _sig_ok, _sig_err = _verify_server_response_signature(data)
                if not _sig_ok:
                    logger.critical(
                        f"SECURITY: Heartbeat response signature invalid: "
                        f"{_sig_err}. Treating as server unreachable."
                    )
                    return False, {'status': 'error', 'message': 'Invalid server response signature'}

                # Check if the server returned an error
                if data.get('status') == 'error':
                    error_msg = data.get('message', 'Unknown error')
                    logger.error(f"Heartbeat error from server: {error_msg}")
                    return False, data
                
                # Store challenge nonce from server for next heartbeat.
                # Only store AFTER signature verification above.
                new_nonce = data.get('challenge_nonce')
                if new_nonce:
                    _store_challenge_nonce(new_nonce)
                
                logger.info("Heartbeat sent successfully")
                return True, data
            
            elif response.status_code == 400:
                # Data validation error
                try:
                    data = response.json()
                    error_msg = data.get('message', 'Invalid request data')
                    details = data.get('details', {})
                    if details:
                        error_msg += f": {details}"
                    logger.warning(f"Heartbeat validation error: {error_msg}")
                    return False, data
                except:
                    logger.warning(f"Heartbeat failed with status 400 (Bad Request)")
                    return False, {'status': 'error', 'message': 'Invalid request data'}
            
            elif response.status_code == 403:
                # License locked (e.g. due to concurrent use)
                try:
                    data = response.json()
                    error_msg = data.get('message', 'License blocked')
                    logger.critical(f"License blocked via heartbeat: {error_msg}")
                    # Make sure is_blocked and block_reason are present in the response
                    if 'is_blocked' not in data:
                        data['is_blocked'] = True
                    if 'block_reason' not in data and error_msg:
                        data['block_reason'] = error_msg
                    return False, data
                except:
                    logger.critical(f"License blocked via heartbeat (status 403)")
                    return False, {'status': 'error', 'message': 'License blocked', 'is_blocked': True, 'block_reason': 'License blocked by server'}
            
            elif response.status_code == 404:
                # The license was not found on the server - we consider it blocked
                logger.critical("License not found on server via heartbeat - blocking license")
                return False, {'status': 'error', 'error': 'License not found', 'is_blocked': True, 'block_reason': 'License not found on server'}
            
            else:
                logger.warning(f"Heartbeat failed with status {response.status_code}")
                try:
                    data = response.json()
                    return False, data
                except:
                    # If it fails to parse the JSON, try to get the text
                    try:
                        error_text = response.text[:200]
                        logger.error(f"Server returned non-JSON response: {error_text}")
                        return False, {'status': 'error', 'message': f'Server error (status {response.status_code})'}
                    except:
                        return False, {'status': 'error', 'message': f'Server error (status {response.status_code})'}
            
        except requests.ConnectionError as e:
            error_msg = f"License server unreachable: {str(e)}"
            logger.warning(error_msg)
            return False, {'status': 'error', 'message': error_msg}
        
        except requests.Timeout as e:
            error_msg = f"Heartbeat timeout: {str(e)}"
            logger.warning(error_msg)
            return False, {'status': 'error', 'message': error_msg}
        
        except Exception as e:
            error_msg = f"Heartbeat error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, {'status': 'error', 'message': error_msg}
        finally:
            _release_heartbeat_lock(lock_key, lock_token)
    
    @classmethod
    def check_license_status(cls, license_key):
        """
        Check license status on the server.

        Args:
            license_key (str): License key

        Returns:
            tuple: (success: bool, status_data: dict or None)
        """
        try:
            url = f"{cls._get_server_url()}status/"
            
            # Preparation of request data
            payload = {
                'license_key': license_key,
                'hardware_id': HardwareFingerprint.generate_fingerprint(),
            }
            
            # Sending a request
            logger.info(f"Checking license status on server: {url}")
            response = requests.post(
                url,
                json=payload,
                timeout=cls._get_timeout(),
                headers={'Content-Type': 'application/json'}
            )
            
            # Response processing
            if response.status_code == 200:
                data = response.json()
                logger.info("License status retrieved successfully")
                return True, data
            
            else:
                logger.warning(f"Status check failed with status {response.status_code}")
                return False, None
            
        except requests.ConnectionError as e:
            logger.warning(f"License server unreachable for status check: {str(e)}")
            return False, None
        
        except requests.Timeout as e:
            logger.warning(f"Status check timeout: {str(e)}")
            return False, None
        
        except Exception as e:
            logger.error(f"Status check error: {str(e)}")
            return False, None
    
    @classmethod
    def report_usage(cls, license_key, usage_data):
        """
        Send detailed usage statistics.

        Args:
            license_key (str): License key
            usage_data (dict): Detailed statistics

        Returns:
            bool: True if sent successfully
        """
        try:
            url = f"{cls._get_server_url()}usage/"
            
            # Preparation of request data
            payload = {
                'license_key': license_key,
                'hardware_id': HardwareFingerprint.generate_fingerprint(),
                'usage_data': usage_data,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Sending a request (asynchronously, we do not wait for a response)
            response = requests.post(
                url,
                json=payload,
                timeout=5,  # Short timeout for usage reports
                headers={'Content-Type': 'application/json'}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            # It is not critical if it was not possible to send usage stats
            logger.debug(f"Usage report failed: {str(e)}")
            return False
    
    @classmethod
    def _collect_usage_stats(cls):
        """
        Collect usage statistics for sending to the server.

        Returns:
            dict: Usage statistics
        """
        try:
            from django.contrib.auth.models import User
            from app_conf.models import Company
            
            stats = {
                'users': {
                    'total': User.objects.count(),
                    'active': User.objects.filter(is_active=True).count(),
                    'superusers': User.objects.filter(is_superuser=True).count(),
                },
                'companies': {
                    'total': Company.objects.count(),
                },
                'timestamp': timezone.now().isoformat(),
            }
            
            # Additional statistics on modules (if required)
            try:
                from app_risk.models import Risk
                stats['risks'] = Risk.objects.count()
            except:
                pass
            
            try:
                from app_compliance.models import ComplianceControl
                stats['compliance_controls'] = ComplianceControl.objects.count()
            except:
                pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Error collecting usage stats: {str(e)}")
            return {}
    
    @classmethod
    def test_connection(cls):
        """
        Test connection to the license server.

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            url = f"{cls._get_server_url()}ping/"
            
            logger.info(f"Testing connection to license server: {url}")
            response = requests.get(
                url,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info("License server connection: OK")
                return True, "Connection successful"
            else:
                logger.warning(f"License server returned status {response.status_code}")
                return False, f"Server returned status {response.status_code}"
            
        except requests.ConnectionError as e:
            logger.error(f"License server unreachable: {str(e)}")
            return False, "Server unreachable"
        
        except requests.Timeout as e:
            logger.error(f"License server timeout: {str(e)}")
            return False, "Connection timeout"
        
        except Exception as e:
            logger.error(f"Connection test error: {str(e)}")
            return False, f"Error: {str(e)}"


class OfflineGracePeriodManager:
    """
    Offline grace period manager.

    Allows the platform to operate offline for a limited time without
    contact with the license server. The unit is hours (not days) for
    finer control of the grace window.
    """

    @staticmethod
    def get_grace_period_hours():
        """
        Get grace period duration from settings (in hours).

        Reads LICENSE_OFFLINE_GRACE_HOURS; if missing, falls back to the legacy
        LICENSE_OFFLINE_GRACE_PERIOD (days) for compatibility with old configs.
        Hard maximum is 48 hours so a misconfiguration cannot open
        an overly wide window.
        """
        hours = getattr(settings, 'LICENSE_OFFLINE_GRACE_HOURS', None)
        if hours is None:
            # Backward compat: old setting in days
            days = getattr(settings, 'LICENSE_OFFLINE_GRACE_PERIOD', 1)
            hours = int(days) * 24
        hours = int(hours)
        # Hard maximum — protection against deliberately large value in settings
        _MAX_HOURS = 48
        if hours > _MAX_HOURS:
            logger.warning(
                f"LICENSE_OFFLINE_GRACE_HOURS={hours} перевищує максимум {_MAX_HOURS} год. "
                f"Застосовується максимум."
            )
            hours = _MAX_HOURS
        return hours

    @classmethod
    def check_grace_period(cls, license_obj):
        """
        Check whether the offline grace period allows operation.

        Returns:
            tuple: (is_valid: bool, message: str)
                True  — grace period is active, OK to work offline
                False — grace period expired OR not started (must contact server)
        """
        try:
            if license_obj.offline_until and license_obj.offline_until > timezone.now():
                remaining = license_obj.offline_until - timezone.now()
                total_seconds = int(remaining.total_seconds())
                hours_left = total_seconds // 3600
                minutes_left = (total_seconds % 3600) // 60
                if hours_left > 0:
                    time_str = f"{hours_left}h {minutes_left}m"
                else:
                    time_str = f"{minutes_left}m"
                return True, f"Offline grace period active ({time_str} remaining)"

            if license_obj.offline_until and license_obj.offline_until <= timezone.now():
                return False, "Offline grace period expired"

            # offline_until is None → no grace period active.
            # Caller MUST attempt a heartbeat; do NOT grant implicit access.
            return False, "No grace period — heartbeat required"

        except Exception as e:
            logger.error(f"Grace period check error: {str(e)}")
            return False, str(e)

    @classmethod
    def start_grace_period(cls, license_obj):
        """
        Start the grace period (when the server is unreachable).

        Args:
            license_obj: SecureLicense model instance
        """
        try:
            from datetime import timedelta

            grace_hours = cls.get_grace_period_hours()
            license_obj.offline_until = timezone.now() + timedelta(hours=grace_hours)
            # Include record_hmac so offline_until modification in DB is detectable.
            license_obj.save(update_fields=['offline_until', 'record_hmac'])

            logger.warning(f"Started offline grace period: {grace_hours} hours")

        except Exception as e:
            logger.error(f"Error starting grace period: {str(e)}")

    @classmethod
    def clear_grace_period(cls, license_obj):
        """
        Clear the grace period (when connection is restored).

        Args:
            license_obj: SecureLicense model instance
        """
        try:
            license_obj.offline_until = None
            # Include record_hmac so offline_until modification in DB is detectable.
            license_obj.save(update_fields=['offline_until', 'record_hmac'])

            logger.info("Cleared offline grace period (connection restored)")

        except Exception as e:
            logger.error(f"Error clearing grace period: {str(e)}")


# For testing
if __name__ == '__main__':
    print("=== License Server API Test ===\n")
    
    # Connection test
    print("Testing connection...")
    success, message = LicenseServerAPI.test_connection()
    print(f"Result: {message}\n")
    
    if success:
        print("License server is reachable!")
    else:
        print("License server is unreachable (offline mode will be used)")

