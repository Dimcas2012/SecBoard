# SecBoard\app_conf\hardware_binding.py
"""
Hardware Fingerprinting System
"""

import hashlib
import hmac
import platform
import socket
import uuid
import subprocess
import os
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_HW_REPORT_SALT = b'SecBoard_HW_Report_Integrity_v1_pR7nZ3'


class HardwareFingerprint:
    """
    Create a unique server fingerprint based on hardware characteristics.

    Combining multiple parameters makes system cloning difficult,
    since the license is bound to a specific server.
    """
    
    @staticmethod
    def get_cpu_id():
        """
        Get the processor identifier.

        Returns:
            str: CPU ID or processor info
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows: Get ProcessorId via WMIC
                output = subprocess.check_output(
                    "wmic cpu get ProcessorId", 
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode('utf-8', errors='ignore')
                
                lines = output.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
                    
            elif system == "Linux":
                # Linux: try to get from /proc/cpuinfo
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if 'Serial' in line or 'processor' in line:
                                parts = line.split(':')
                                if len(parts) > 1:
                                    return parts[1].strip()
                except FileNotFoundError:
                    pass
            
            # Fallback: use platform.processor()
            return platform.processor() or "unknown_cpu"
            
        except Exception as e:
            logger.warning(f"Failed to get CPU ID: {str(e)}")
            return platform.processor() or "unknown_cpu"
    
    @staticmethod
    def get_motherboard_id():
        """
        Get the motherboard identifier.

        Returns:
            str: Motherboard serial, or hostname if unavailable
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows: Get SerialNumber via WMIC
                output = subprocess.check_output(
                    "wmic baseboard get SerialNumber",
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode('utf-8', errors='ignore')
                
                lines = output.strip().split('\n')
                if len(lines) > 1:
                    serial = lines[1].strip()
                    if serial and serial.lower() not in ['to be filled by o.e.m.', 'default string']:
                        return serial
                        
            elif system == "Linux":
                # Linux: try to get from DMI
                dmi_paths = [
                    '/sys/class/dmi/id/board_serial',
                    '/sys/class/dmi/id/product_uuid',
                    '/sys/class/dmi/id/board_vendor'
                ]
                
                for dmi_path in dmi_paths:
                    try:
                        with open(dmi_path, 'r') as f:
                            value = f.read().strip()
                            if value and value.lower() not in ['to be filled by o.e.m.', 'default string']:
                                return value
                    except (FileNotFoundError, PermissionError):
                        continue
            
            # Fallback: hostname
            return socket.gethostname()
            
        except Exception as e:
            logger.warning(f"Failed to get motherboard ID: {str(e)}")
            return socket.gethostname()
    
    @staticmethod
    def get_mac_addresses():
        """
        Get MAC addresses of all network interfaces.

        Returns:
            list: Sorted list of MAC addresses
        """
        mac_list = []
        
        try:
            system = platform.system()
            
            if system == "Linux":
                # Linux: reading from /sys/class/net/
                try:
                    net_dir = '/sys/class/net/'
                    if os.path.exists(net_dir):
                        for interface in os.listdir(net_dir):
                            address_file = os.path.join(net_dir, interface, 'address')
                            try:
                                with open(address_file, 'r') as f:
                                    mac = f.read().strip()
                                    # We filter zero and loopback addresses
                                    if mac and mac != '00:00:00:00:00:00' and not mac.startswith('00:00:00'):
                                        mac_list.append(mac.upper())
                            except (FileNotFoundError, PermissionError):
                                continue
                except Exception:
                    pass
            
            # Fallback or Windows: use uuid.getnode()
            if not mac_list:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                              for elements in range(0, 2*6, 2)][::-1])
                if mac and mac != '00:00:00:00:00:00':
                    mac_list.append(mac.upper())
            
            # Remove duplicates and sort for consistency
            # IMPORTANT: Sorting ensures a stable order between reboots
            mac_list = sorted(list(set(mac_list)))
            logger.debug(f"MAC addresses collected: {mac_list}")
            
        except Exception as e:
            logger.warning(f"Failed to get MAC addresses: {str(e)}")
            # Fallback to uuid.getnode()
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                          for elements in range(0, 2*6, 2)][::-1])
            mac_list = [mac.upper()]
        
        return mac_list if mac_list else ["00:00:00:00:00:00"]
    
    @staticmethod
    def get_disk_serial():
        """
        Get the system disk serial number.

        Returns:
            str: Disk serial, or an empty string
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows: Get SerialNumber via WMIC
                output = subprocess.check_output(
                    "wmic diskdrive get SerialNumber",
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode('utf-8', errors='ignore')
                
                lines = output.strip().split('\n')
                if len(lines) > 1:
                    serial = lines[1].strip()
                    if serial:
                        return serial
                        
            elif system == "Linux":
                # Linux: try lsblk
                try:
                    output = subprocess.check_output(
                        "lsblk -o SERIAL -n",
                        shell=True,
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8', errors='ignore')
                    
                    lines = output.strip().split('\n')
                    if lines and lines[0]:
                        return lines[0].strip()
                except Exception:
                    pass
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to get disk serial: {str(e)}")
            return ""
    
    @staticmethod
    def get_system_uuid():
        """
        Get the system UUID (if available).

        Returns:
            str: System UUID, or an empty string
        """
        try:
            system = platform.system()
            
            if system == "Linux":
                # Linux: try to get from DMI
                try:
                    with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                        return f.read().strip()
                except (FileNotFoundError, PermissionError):
                    pass
            
            elif system == "Windows":
                # Windows: via WMIC
                try:
                    output = subprocess.check_output(
                        "wmic csproduct get UUID",
                        shell=True,
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8', errors='ignore')
                    
                    lines = output.strip().split('\n')
                    if len(lines) > 1:
                        return lines[1].strip()
                except Exception:
                    pass
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to get system UUID: {str(e)}")
            return ""
    
    @staticmethod
    def get_machine_id():
        """
        Get machine-id (Linux) or an equivalent unique identifier.

        Returns:
            str: Machine ID, or an empty string
        """
        try:
            system = platform.system()
            
            if system == "Linux":
                # Linux: /etc/machine-id (unique for each system)
                machine_id_paths = [
                    '/etc/machine-id',
                    '/var/lib/dbus/machine-id'
                ]
                
                for path in machine_id_paths:
                    try:
                        if os.path.exists(path):
                            with open(path, 'r') as f:
                                machine_id = f.read().strip()
                                if machine_id:
                                    return machine_id
                    except (FileNotFoundError, PermissionError):
                        continue
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to get machine ID: {str(e)}")
            return ""

    @staticmethod
    def get_root_fs_uuid():
        """Root filesystem UUID — stable across reboots, tied to specific partition."""
        try:
            if platform.system() != "Linux":
                return ""
            output = subprocess.check_output(
                "findmnt -n -o UUID /",
                shell=True, stderr=subprocess.DEVNULL
            ).decode('utf-8', errors='ignore').strip()
            return output if output else ""
        except Exception as e:
            logger.warning(f"Failed to get root FS UUID: {e}")
            return ""

    @staticmethod
    def get_bios_info():
        """BIOS vendor, version, date — identifies VM / hardware platform."""
        info = {'bios_vendor': '', 'bios_version': '', 'bios_date': ''}
        if platform.system() != "Linux":
            return info
        dmi_map = {
            'bios_vendor': '/sys/class/dmi/id/bios_vendor',
            'bios_version': '/sys/class/dmi/id/bios_version',
            'bios_date': '/sys/class/dmi/id/bios_date',
        }
        for key, path in dmi_map.items():
            try:
                with open(path, 'r') as f:
                    val = f.read().strip()
                    if val and val.lower() not in ('to be filled by o.e.m.', 'default string'):
                        info[key] = val
            except (FileNotFoundError, PermissionError):
                pass
        return info

    @staticmethod
    def get_product_name():
        """DMI product name — e.g. 'Standard PC (i440FX + PIIX, 1996)'."""
        if platform.system() != "Linux":
            return ""
        try:
            with open('/sys/class/dmi/id/product_name', 'r') as f:
                val = f.read().strip()
                if val and val.lower() not in ('to be filled by o.e.m.', 'default string'):
                    return val
        except (FileNotFoundError, PermissionError):
            pass
        return ""

    @staticmethod
    def get_total_ram_mb():
        """Total physical RAM in MB — relatively stable hardware characteristic."""
        try:
            if platform.system() == "Linux":
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            kb = int(line.split()[1])
                            return kb // 1024
        except Exception as e:
            logger.warning(f"Failed to get total RAM: {e}")
        return 0

    @classmethod
    def get_extended_components(cls):
        """
        Extended hardware components for enhanced binding verification.
        NOT mixed into generate_fingerprint() — preserves backward compatibility.
        """
        base = cls.get_hardware_components(include_server_id=False)
        bios = cls.get_bios_info()
        base['root_fs_uuid'] = cls.get_root_fs_uuid()
        base['bios_vendor'] = bios['bios_vendor']
        base['bios_version'] = bios['bios_version']
        base['bios_date'] = bios['bios_date']
        base['product_name'] = cls.get_product_name()
        base['total_ram_mb'] = cls.get_total_ram_mb()
        return base

    @classmethod
    def _hw_report_path(cls):
        try:
            from django.conf import settings
            base_dir = getattr(settings, 'BASE_DIR', '')
        except Exception:
            base_dir = ''
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return Path(base_dir) / '.secboard_hw_report'

    @classmethod
    def _sign_report(cls, report_data, license_key_hash=''):
        """
        HMAC-sign the hardware report.

        Key = SHA256(salt + machine_id + ':' + license_key_hash)

        When license_key_hash is provided the key binds the report to a specific
        license entry in the database.  An attacker with filesystem-only access
        cannot reproduce this value without also querying the database, which
        raises the bar significantly compared to the legacy scheme that used
        only machine_id (readable from /etc/machine-id) and a static salt.
        """
        machine_id = cls.get_machine_id() or socket.gethostname()
        binding = license_key_hash.encode('utf-8') if license_key_hash else b''
        key = hashlib.sha256(
            _HW_REPORT_SALT + machine_id.encode('utf-8') + b':' + binding
        ).digest()
        canonical = json.dumps(report_data, sort_keys=True)
        return hmac.new(key, canonical.encode('utf-8'), hashlib.sha256).hexdigest()

    @classmethod
    def create_signed_hardware_report(cls, license_key_hash=''):
        """
        Collect extended hardware components, sign with HMAC, persist to .secboard_hw_report.

        Args:
            license_key_hash: SHA-256 hex digest of the active license key
                              (from SecureLicense.license_key_hash).  When
                              provided the report is written as version 3 and
                              the HMAC key is bound to this value.
        """
        components = cls.get_extended_components()

        # binding_key_id: SHA-256 of license_key_hash stored in the report so
        # verify_hardware_report() can detect licence-key changes and stale bindings.
        binding_key_id = (
            hashlib.sha256(license_key_hash.encode('utf-8')).hexdigest()
            if license_key_hash else ''
        )

        report = {
            'version': 3 if license_key_hash else 2,
            'binding_key_id': binding_key_id,
            'components': components,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        report['hmac'] = cls._sign_report(report['components'], license_key_hash)

        report_path = cls._hw_report_path()
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            report_path.chmod(0o600)
            version_label = f"v{report['version']}" + (' (bound)' if license_key_hash else ' (unbound)')
            logger.info(f"Signed hardware report created: {version_label}")
        except Exception as e:
            logger.error(f"Failed to write hardware report: {e}")
        return report

    @classmethod
    def verify_hardware_report(cls, tolerance=2, license_key_hash='', allow_create=True):
        """
        Verify the signed hardware report against current hardware.

        Version 3 reports are HMAC-bound to the active license key hash so that
        forging requires both filesystem access AND database read access.

        Version 2 (legacy) reports are automatically upgraded to version 3 on
        the first successful verification pass — the new report is written from
        the current (live) hardware state, not from the legacy baseline.

        allow_create — controls what happens when the report file is absent:
          True  (default): create an initial report (used during first-time
                           activation from license_manager.py / tests).
          False:           treat the missing file as a security event — log a
                           CRITICAL message and return valid=False.  Pass this
                           flag when verifying an ESTABLISHED license so that
                           deliberate deletion of the report file cannot silently
                           reset the hardware baseline.

        Returns:
            dict: valid, report_intact, drift_count, changed, missing_report
        """
        result = {
            'valid': False,
            'report_intact': False,
            'drift_count': 0,
            'changed': [],
            'missing_report': False,
        }

        report_path = cls._hw_report_path()
        if not report_path.exists():
            result['missing_report'] = True
            if allow_create:
                logger.warning("Hardware report file missing — creating initial report")
                cls.create_signed_hardware_report(license_key_hash)
                result['valid'] = True
            else:
                logger.critical(
                    "SECURITY: Hardware report file (.secboard_hw_report) is missing "
                    "for an established license. Deliberate deletion can be used to "
                    "reset the hardware baseline and bypass drift detection. "
                    "Re-activate the license to create a new authorised baseline."
                )
                result['valid'] = False
            return result

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read hardware report: {e}")
            return result

        stored_hmac = report.get('hmac', '')
        stored_components = report.get('components', {})
        stored_version = report.get('version', 2)
        stored_binding_key_id = report.get('binding_key_id', '')

        # ── Version 3: binding-aware verification ────────────────────────────
        if stored_version >= 3:
            # A v3 report with an empty binding_key_id is structurally invalid —
            # it may indicate the field was deliberately cleared to bypass the
            # binding check (downgrade attack).
            if not stored_binding_key_id:
                logger.critical(
                    "SECURITY: Hardware report is version 3 but has no binding_key_id — "
                    "possible downgrade tampering. Re-create via license re-activation."
                )
                return result

            expected_binding_id = (
                hashlib.sha256(license_key_hash.encode('utf-8')).hexdigest()
                if license_key_hash else ''
            )

            if license_key_hash and stored_binding_key_id != expected_binding_id:
                # License key was rotated / re-activated — re-create the report
                # from current hardware so the new binding is established.
                logger.warning(
                    "Hardware report binding outdated (license key changed) — "
                    "re-creating report with new binding"
                )
                cls.create_signed_hardware_report(license_key_hash)
                result['valid'] = True
                return result

            expected_hmac = cls._sign_report(stored_components, license_key_hash)
            if not hmac.compare_digest(stored_hmac, expected_hmac):
                logger.critical(
                    "SECURITY: Hardware report HMAC mismatch (bound) — "
                    "file has been tampered with or license_key_hash mismatch"
                )
                return result

        # ── Version 2 (legacy): upgrade path ─────────────────────────────────
        else:
            expected_hmac_legacy = cls._sign_report(stored_components, '')
            if not hmac.compare_digest(stored_hmac, expected_hmac_legacy):
                logger.critical(
                    "SECURITY: Hardware report HMAC mismatch (legacy) — "
                    "file has been tampered with"
                )
                return result

            # Legacy HMAC is valid — upgrade to v3 by re-creating from current
            # hardware.  We intentionally do NOT carry the old (unbound) baseline
            # forward; a fresh snapshot of current hardware serves as the new baseline.
            if license_key_hash:
                logger.info(
                    "Hardware report is legacy (v2, unbound) — upgrading to v3 "
                    "with license binding (new hardware baseline recorded)"
                )
                cls.create_signed_hardware_report(license_key_hash)
                result['valid'] = True
                return result

        result['report_intact'] = True

        # ── Component drift check ─────────────────────────────────────────────
        current = cls.get_extended_components()

        immutable_keys = {
            'cpu_id', 'motherboard_id', 'system_uuid', 'machine_id',
            'root_fs_uuid', 'bios_vendor', 'bios_version', 'bios_date',
            'product_name',
        }
        semi_stable_keys = {
            'mac_addresses', 'disk_serial', 'hostname', 'fqdn', 'domain',
            'total_ram_mb',
        }

        changed = []
        for key in immutable_keys:
            stored_val = stored_components.get(key, '')
            current_val = current.get(key, '')
            if stored_val and current_val and stored_val != current_val:
                changed.append(key)

        for key in semi_stable_keys:
            stored_val = stored_components.get(key, '')
            current_val = current.get(key, '')
            if stored_val and current_val and stored_val != current_val:
                changed.append(key)

        result['drift_count'] = len(changed)
        result['changed'] = changed
        result['valid'] = len(changed) <= tolerance

        if changed:
            logger.warning(
                f"Hardware drift detected: {len(changed)} component(s) changed: "
                f"{', '.join(changed)} (tolerance={tolerance}, valid={result['valid']})"
            )
        else:
            logger.info("Hardware report verification passed — no drift detected")

        return result

    @staticmethod
    def get_server_id():
        """
        Get a unique Server ID based on Hardware ID + HTTP_HOST from the first request.

        Server ID = hash(Hardware ID + HTTP_HOST from the first HTTP request)

        IMPORTANT:
        - Server ID is saved to a file after first generation to ensure stability.
        - Before using a saved Server ID, it is verified against the current HTTP_HOST.
        - If the saved Server ID does not match the current HTTP_HOST, a new one is generated.
        - This ensures Server ID uniqueness for different domains (prod.secboard.online vs
          test.secboard.online) even when they run on the same machine with the same Hardware ID.

        Returns:
            str: Unique Server ID (64 hex characters, full SHA256)
        """
        try:
            from django.conf import settings
            import hashlib
            
            base_dir = getattr(settings, 'BASE_DIR', '')
            if not base_dir:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Files to save
            server_id_file = Path(base_dir) / '.secboard_server_id'
            host_file = Path(base_dir) / '.secboard_first_host'
            
            # Generate Hardware ID (required for verification and generation)
            hardware_id = HardwareFingerprint._generate_fingerprint_without_server_id()
            
            # Get the HTTP_HOST from the first request
            first_host = None
            if host_file.exists():
                try:
                    with open(host_file, 'r') as f:
                        first_host = f.read().strip()
                except Exception as e:
                    logger.error(f"Could not read first host file: {str(e)}")
            
            # If the Server ID is already saved, check if it matches the current HTTP_HOST
            if server_id_file.exists() and first_host and first_host not in ('testserver', 'localhost', '127.0.0.1'):
                try:
                    with open(server_id_file, 'r') as f:
                        saved_server_id = f.read().strip()
                        # Check length (SHA256 hex = 64 characters)
                        if saved_server_id and len(saved_server_id) == 64:
                            # Check if the Server ID matches the current HTTP_HOST
                            # We generate the expected Server ID for the current HTTP_HOST
                            expected_combined = f"{hardware_id}:{first_host}"
                            expected_server_id = hashlib.sha256(expected_combined.encode('utf-8')).hexdigest()
                            
                            if saved_server_id == expected_server_id:
                                logger.info(f"Using saved Server ID from file: {saved_server_id[:16]}... (matches HTTP_HOST: {first_host})")
                                return saved_server_id
                            else:
                                logger.warning(
                                    f"Saved Server ID does not match current HTTP_HOST ({first_host}). "
                                    f"Expected: {expected_server_id[:16]}..., Saved: {saved_server_id[:16]}... "
                                    f"Regenerating Server ID..."
                                )
                        else:
                            logger.warning(f"Saved Server ID has wrong length: {len(saved_server_id)} (expected 64), regenerating...")
                except Exception as e:
                    logger.warning(f"Could not read saved Server ID: {str(e)}")
            
            # We generate a new Server ID based on Hardware ID + HTTP_HOST
            if first_host and first_host not in ('testserver', 'localhost', '127.0.0.1'):
                # Create Server ID based on Hardware ID + HTTP_HOST
                combined = f"{hardware_id}:{first_host}"
                server_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()
                # Check the length
                if len(server_id) != 64:
                    logger.error(f"Generated Server ID has wrong length: {len(server_id)} (expected 64)")
                logger.info(f"Server ID generated from Hardware ID + HTTP_HOST: {first_host} -> {server_id[:16]}... (length: {len(server_id)})")
                # Save for future use
                try:
                    server_id_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(server_id_file, 'w') as f:
                        f.write(server_id)
                    server_id_file.chmod(0o600)
                    logger.info(f"Server ID saved to file for stability: {server_id[:16]}...")
                except Exception as e:
                    logger.warning(f"Could not save Server ID to file: {str(e)}")
                return server_id
            elif first_host:
                logger.warning(f"HTTP_HOST file exists but contains invalid value: {first_host}")
            
            # If the file is not there, try to get it from the environment variable
            if not first_host:
                instance_id = os.environ.get('SECBOARD_INSTANCE_ID')
                if instance_id:
                    combined = f"{hardware_id}:{instance_id}"
                    server_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()
                    logger.info(f"Server ID generated from Hardware ID + SECBOARD_INSTANCE_ID: {instance_id} -> {server_id[:16]}...")
                    # Save for future use
                    try:
                        server_id_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(server_id_file, 'w') as f:
                            f.write(server_id)
                        server_id_file.chmod(0o600)
                    except Exception:
                        pass
                    return server_id
                else:
                    # Fallback to hostname (stable, does not change)
                    hostname = socket.gethostname()
                    combined = f"{hardware_id}:{hostname}"
                    server_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()
                    logger.warning(f"HTTP_HOST file not found, using hostname as fallback: {hostname} -> {server_id[:16]}...")
                    # Save for future use
                    try:
                        server_id_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(server_id_file, 'w') as f:
                            f.write(server_id)
                        server_id_file.chmod(0o600)
                        logger.info(f"Server ID saved to file for stability")
                    except Exception as e:
                        logger.warning(f"Could not save Server ID to file: {str(e)}")
                    return server_id
            
            # If first_host exists but is not valid, use hostname
            hostname = socket.gethostname()
            combined = f"{hardware_id}:{hostname}"
            server_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()
            logger.warning(f"Using hostname as fallback: {hostname} -> {server_id[:16]}...")
            # Save for future use
            try:
                server_id_file.parent.mkdir(parents=True, exist_ok=True)
                with open(server_id_file, 'w') as f:
                    f.write(server_id)
                server_id_file.chmod(0o600)
            except Exception:
                pass
            return server_id
            
        except Exception as e:
            logger.error(f"Failed to get server ID: {str(e)}")
            # The last fallback is Hardware ID + hostname
            import hashlib
            try:
                hardware_id = HardwareFingerprint._generate_fingerprint_without_server_id()
                hostname = socket.gethostname()
                combined = f"{hardware_id}:{hostname}"
                fallback_server_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()
                # Try to save the fallback Server ID
                try:
                    server_id_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(server_id_file, 'w') as f:
                        f.write(fallback_server_id)
                    server_id_file.chmod(0o600)
                except:
                    pass
                return fallback_server_id
            except:
                fallback = hashlib.sha256(socket.gethostname().encode()).hexdigest()
                # Try to save the fallback Server ID
                try:
                    server_id_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(server_id_file, 'w') as f:
                        f.write(fallback)
                    server_id_file.chmod(0o600)
                except:
                    pass
                return fallback
    
    @classmethod
    def get_hardware_components(cls, include_server_id=False):
        """
        Get all hardware components as a dictionary.

        Args:
            include_server_id (bool): Whether to include server_id in components
                (default False to avoid circular dependency)

        Returns:
            dict: Dictionary of all hardware characteristics
        """
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        
        components = {
            'cpu_id': cls.get_cpu_id(),
            'motherboard_id': cls.get_motherboard_id(),
            'mac_addresses': cls.get_mac_addresses(),
            'disk_serial': cls.get_disk_serial(),
            'system_uuid': cls.get_system_uuid(),
            'hostname': hostname,
            'fqdn': fqdn,  # Full domain name
            'domain': fqdn.split('.', 1)[1] if '.' in fqdn and fqdn != hostname else '',
            'machine_id': cls.get_machine_id(),  # Unique machine-id
            'platform': platform.system(),
            'machine': platform.machine(),
        }
        
        # Add server_id only if explicitly requested (to avoid circular dependency)
        if include_server_id:
            server_id = cls.get_server_id()
            components['server_id'] = server_id  # Server ID = hash (Hardware ID + HTTP_HOST from the first request)
            logger.debug(f"Server ID included in components: {server_id[:16]}...")
        
        logger.info(f"Hardware components collected: {list(components.keys())}")
        return components
    
    @classmethod
    def _generate_fingerprint_without_server_id(cls):
        """
        Internal method to generate Hardware ID without server_id (avoids circular dependency).

        Returns:
            str: SHA256 hash of hardware components (64 characters)
        """
        try:
            # We get all components WITHOUT server_id (to avoid cyclic dependency)
            components = cls.get_hardware_components(include_server_id=False)
            
            # Component logging for diagnostics (keys and short values ​​only)
            component_summary = {}
            for key, value in components.items():
                if isinstance(value, list):
                    component_summary[key] = f"[{len(value)} items]"
                elif isinstance(value, str):
                    component_summary[key] = value[:32] + "..." if len(value) > 32 else value
                else:
                    component_summary[key] = str(value)[:32] + "..." if len(str(value)) > 32 else str(value)
            
            logger.debug(f"Hardware components for fingerprint: {json.dumps(component_summary, indent=2)}")
            
            # We create a canonical representation (sorted keys)
            fingerprint_string = json.dumps(components, sort_keys=True)
            
            # We create a SHA256 hash
            fingerprint_hash = hashlib.sha256(fingerprint_string.encode('utf-8')).hexdigest()
            
            logger.info(f"Hardware fingerprint generated: {fingerprint_hash[:16]}... (length: {len(fingerprint_hash)})")
            return fingerprint_hash
            
        except Exception as e:
            logger.error(f"Failed to generate hardware fingerprint: {str(e)}")
            # Fallback: minimum fingerprint based on hostname and MAC
            fallback = f"{socket.gethostname()}:{uuid.getnode()}"
            return hashlib.sha256(fallback.encode('utf-8')).hexdigest()
    
    @classmethod
    def generate_fingerprint(cls):
        """
        Generate a unique server fingerprint.

        Combines several hardware parameters to create a stable
        yet unique server identifier.

        Returns:
            str: SHA256 hash of hardware components (64 characters)
        """
        # We use an internal method without server_id to avoid cyclic dependency
        return cls._generate_fingerprint_without_server_id()
    
    @classmethod
    def verify_fingerprint(cls, stored_fingerprint, tolerance=1):
        """
        Verify fingerprint with tolerance for changes.

        Args:
            stored_fingerprint (str): SHA-256 hash of hardware components
                (stored in the license or test).
            tolerance (int): Maximum number of components that may change
                without rejection:
                0 — exact hash match only
                1 — one component may change (e.g. MAC)
                2 — two components may change

        Returns:
            bool: True if the fingerprint is valid, False otherwise

        Algorithm:
            1. If hashes match — True (exact match).
            2. tolerance == 0 → False.
            3. tolerance > 0 → load stored components from .secboard_hw_report
               and compare component-by-component with current hardware data.
               If the number of changes ≤ tolerance — True. If hw_report is
               missing or corrupted — safe fallback to False.
        """
        try:
            current_fingerprint = cls.generate_fingerprint()

            # Exact match
            if current_fingerprint == stored_fingerprint:
                logger.info("Hardware fingerprint match: EXACT")
                return True

            # Zero tolerance is an exact match only
            if tolerance == 0:
                logger.warning(
                    f"Hardware fingerprint mismatch (tolerance=0): "
                    f"stored={stored_fingerprint[:16]}..., current={current_fingerprint[:16]}..."
                )
                return False

            # ── Component comparison via hw_report ──────────────────────────
            # stored_fingerprint is just a hash; to know exactly which components
            # have changed, we read the saved components from .secboard_hw_report.
            report_path = cls._hw_report_path()
            if not report_path.exists():
                logger.warning(
                    f"Hardware fingerprint mismatch and hw_report missing — "
                    f"cannot perform tolerance comparison (tolerance={tolerance}). "
                    f"stored={stored_fingerprint[:16]}..."
                )
                return False

            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    report = json.load(f)
            except Exception as read_err:
                logger.error(
                    f"Hardware fingerprint tolerance check: failed to read hw_report: {read_err}"
                )
                return False

            stored_components = report.get('components', {})
            if not stored_components:
                logger.warning("Hardware fingerprint tolerance check: hw_report has no components")
                return False

            current_components = cls.get_hardware_components(include_server_id=False)

            # Monitored component sets
            tracked_keys = {
                'cpu_id', 'motherboard_id', 'system_uuid', 'machine_id',
                'root_fs_uuid', 'bios_vendor', 'bios_version', 'bios_date',
                'product_name', 'mac_addresses', 'disk_serial',
                'hostname', 'fqdn', 'domain', 'total_ram_mb',
            }

            changed = []
            for key in tracked_keys:
                stored_val = stored_components.get(key, '')
                current_val = current_components.get(key, '')
                # We compare only if both values ​​are not empty —
                # a missing value in one of the parties is not considered a change
                if stored_val and current_val and stored_val != current_val:
                    changed.append(key)

            drift_count = len(changed)
            is_within_tolerance = drift_count <= tolerance

            if is_within_tolerance:
                logger.info(
                    f"Hardware fingerprint match within tolerance: "
                    f"{drift_count} component(s) changed "
                    f"({', '.join(changed) if changed else 'none'}), "
                    f"tolerance={tolerance}"
                )
            else:
                logger.warning(
                    f"Hardware fingerprint mismatch: {drift_count} component(s) changed "
                    f"({', '.join(changed)}), tolerance={tolerance} — rejected"
                )
            return is_within_tolerance

        except Exception as e:
            logger.error(f"Hardware fingerprint verification error: {str(e)}")
            return False
    
    @classmethod
    def get_fingerprint_info(cls):
        """
        Get detailed fingerprint information for user display.

        Returns:
            dict: Hardware component and fingerprint information
        """
        components = cls.get_hardware_components(include_server_id=True)
        fingerprint = cls.generate_fingerprint()
        extended = cls.get_extended_components()

        return {
            'fingerprint': fingerprint,
            'fingerprint_short': fingerprint[:16] + '...',
            'components': {
                'hostname': components['hostname'],
                'platform': components['platform'],
                'machine': components['machine'],
                'cpu_id': components['cpu_id'][:50] + '...' if len(components['cpu_id']) > 50 else components['cpu_id'],
                'mac_addresses_count': len(components['mac_addresses']),
                'has_disk_serial': bool(components['disk_serial']),
                'has_system_uuid': bool(components['system_uuid']),
            },
            'extended': {
                'root_fs_uuid': (extended.get('root_fs_uuid', '')[:16] + '...')
                if extended.get('root_fs_uuid') else '',
                'bios_vendor': extended.get('bios_vendor', ''),
                'product_name': extended.get('product_name', ''),
                'total_ram_mb': extended.get('total_ram_mb', 0),
            },
        }


# For testing (delete in production)
if __name__ == '__main__':
    print("=== Hardware Fingerprinting Test ===\n")
    
    # Obtaining all components
    print("Hardware Components:")
    components = HardwareFingerprint.get_hardware_components(include_server_id=True)  # Include server_id for display
    for key, value in components.items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(value)}")
        else:
            print(f"  {key}: {value}")
    
    print("\n" + "="*50)
    
    # Fingerprint generation
    fingerprint = HardwareFingerprint.generate_fingerprint()
    print(f"\nHardware Fingerprint: {fingerprint}")
    print(f"Short version: {fingerprint[:16]}...")
    
    # Information for the user
    print("\n" + "="*50)
    print("\nFingerprint Info:")
    info = HardwareFingerprint.get_fingerprint_info()
    print(f"Fingerprint: {info['fingerprint_short']}")
    print(f"Components: {json.dumps(info['components'], indent=2)}")
    
    # Verification test
    print("\n" + "="*50)
    print("\nVerification Test:")
    result = HardwareFingerprint.verify_fingerprint(fingerprint, tolerance=0)
    print(f"Verification result: {'PASS' if result else 'FAIL'}")

