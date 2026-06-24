# SecBoard\app_conf\license_crypto.py
"""
RSA-based License Signature System
"""

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import base64
import json
import logging
import hashlib
import struct

logger = logging.getLogger(__name__)


def _xor_bytes(data, key):
    """XOR data with repeating key."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


# Machine-ID binding for this specific build.
#   ''         — generic build: works on any machine, binding check is skipped.
#   non-empty  — machine-specific build: runtime /etc/machine-id must match.
# Populated by the build pipeline (obfuscate_cython_only.py Step 2.5c) when
# SECBOARD_BUILD_MACHINE_ID environment variable is set at build time.
_MACHINE_ID_BINDING = ''


def _get_runtime_machine_id():
    """Read the machine-id of the running host from the filesystem."""
    _mpaths = (b'/etc/machine-id', b'/var/lib/dbus/machine-id')
    for _mp in _mpaths:
        try:
            with open(_mp, 'rb') as _mf:
                _mv = _mf.read().strip()
                if _mv:
                    return _mv
        except (OSError, IOError):
            pass
    try:
        import socket as _sk
        return _sk.gethostname().encode('utf-8')
    except Exception:
        return b'\x00'


def _derive_runtime_key():
    """
    Derive the XOR decryption key for the embedded RSA public key material.

    Security improvements over the original single-round SHA-256:

    1. Component bytes are stored as hex arrays — they do NOT appear as
       printable strings in `strings` output of the compiled .so binary.
    2. Two-round derivation: SHA-256 seed → HMAC-SHA-256 final key.
       This produces more code paths for a static analyser to trace compared
       to a single SHA-256 hash.
    3. Optional machine-ID binding: when _MACHINE_ID_BINDING is non-empty
       (machine-specific build), the runtime /etc/machine-id is mixed into
       the SHA-256 seed so the XOR decryption key is unique to the target
       machine.  A binary exported to a different machine for offline analysis
       produces the wrong key and decrypts to garbage.
    """
    import hmac as _hm

    # Hex byte arrays — no printable ASCII literals that appear in `strings`.
    _c0 = bytes([0x53, 0x65, 0x63, 0x42, 0x6f, 0x61, 0x72, 0x64])             # SecBoard
    _c1 = bytes([0x4c, 0x69, 0x63, 0x65, 0x6e, 0x73, 0x65, 0x43, 0x72,
                 0x79, 0x70, 0x74, 0x6f])                                       # LicenseCrypto
    _c2 = bytes([0x76, 0x65, 0x72, 0x69, 0x66, 0x79, 0x5f, 0x6c, 0x69,
                 0x63, 0x65, 0x6e, 0x73, 0x65, 0x5f, 0x73, 0x69, 0x67,
                 0x6e, 0x61, 0x74, 0x75, 0x72, 0x65])                          # verify_license_signature
    _c3 = struct.pack('>I', 0x5345434F)
    _c4 = bytes([0x73, 0x65, 0x63, 0x62, 0x6f, 0x61, 0x72, 0x64])             # secboard

    # Round 1: SHA-256 seed from all components
    _h1 = hashlib.sha256()
    for _c in (_c0, _c1, _c2, _c3, _c4):
        _h1.update(_c)

    # Machine-ID binding: mixes /etc/machine-id into the seed so that the
    # XOR key is unique per machine.  The build pipeline encrypts the PEM
    # using the same machine_id (via SECBOARD_BUILD_MACHINE_ID env var), so
    # decryption ONLY works on the target machine.
    if _MACHINE_ID_BINDING:
        _h1.update(_get_runtime_machine_id())

    _seed = _h1.digest()

    # Round 2: HMAC-SHA-256 — adds a second derivation step for added
    # complexity compared to a single hash.
    return _hm.new(_seed, _c0 + _c3 + _c4, hashlib.sha256).digest()


def _verify_machine_binding():
    """
    Enforce machine-ID binding before the public key PEM is returned.

    Provides early, explicit failure with a clear log message when this
    machine-specific build is deployed to the wrong machine.  Without this
    check the failure mode would be a silent garbage decrypt followed by a
    cryptographic library exception with a less informative message.

    No-op for generic builds (_MACHINE_ID_BINDING == '').
    """
    if not _MACHINE_ID_BINDING:
        return
    import hmac as _hm2
    _runtime_mid = _get_runtime_machine_id().decode('utf-8', errors='replace').strip()
    _expected_mid = _MACHINE_ID_BINDING.strip()
    if not _hm2.compare_digest(_runtime_mid, _expected_mid):
        logger.critical(
            "SECURITY: Machine-ID binding mismatch — this build was created for "
            "a different machine, or _MACHINE_ID_BINDING has been tampered with. "
            f"binding_prefix={_expected_mid[:8]}..., "
            f"runtime_prefix={_runtime_mid[:8]}..."
        )
        raise RuntimeError(
            "Machine-ID binding mismatch — build deployed to wrong machine "
            "or _MACHINE_ID_BINDING tampered"
        )


# --- Obfuscated RSA public key storage ---
# Key is XOR-encrypted with a runtime-derived key and split into chunks.
# This prevents trivial extraction via `strings` on the compiled .so binary.
# The actual PEM key is reconstructed at runtime by _reconstruct_public_key().

_K_CHUNKS = [
    b'\x98\xf8\x2d\x18\x5e\x09\xeb\x14\xa0\xd4\x17\x5d\x19\x06\x62\x09'
    b'\x18\x0c\x46\xf5\x14\xd5\x16\xe0\xf7\x2b\xb2\x14\x0d\x27\xd8\x51',
]

_OBFUSCATED_KEY_B64 = None
_RAW_PUBLIC_KEY_PEM = None


def _reconstruct_public_key():
    """Reconstruct the PEM public key from obfuscated storage at runtime."""
    global _RAW_PUBLIC_KEY_PEM
    if _RAW_PUBLIC_KEY_PEM is not None:
        return _RAW_PUBLIC_KEY_PEM

    # Machine-binding check — runs before the PEM is returned so that
    # machine-specific builds fail fast with a clear message rather than
    # producing a confusing decryption error downstream.
    _verify_machine_binding()

    # Fallback: use the embedded PEM directly (set during build by obfuscate step).
    # In source code we keep the original for development; the build pipeline
    # will replace this block with the obfuscated version.
    _RAW_PUBLIC_KEY_PEM = (
        b"-----BEGIN PUBLIC KEY-----\n"
        b"MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAjeSfN++qpMBJAjtdZCcV\n"
        b"5fIIhhIu8ygmmZDqIpYqoNwJelh19v9oTgPkF8RWJCtS/37Mrth19ozY+IyY33c2\n"
        b"gEPhUnkNcvKLA1n+qvf8vOo5NGJsQviC5wsXpu02wqgLOn7B3hy9XBJ/nxSCWrZX\n"
        b"lwMy9UkGGjWhknOeWC5uHvA9maEXngZKAvUFt+F5djUU4GLpY71J6/096HNF7Pph\n"
        b"X9ak16Kpdsz9chc/6LGo73nb3mz6dfYAy1fwIIolmiR5YT0+EHBg/ei2HlWay+ha\n"
        b"IQvsJRlJ2cZh9au8e+AzTMQdsmuHjhL66iO+3kHrrzJvSDJtJySxdErbKETuBo5Z\n"
        b"nYri5G5wQI6B6F+Unf55AccFB4HDI+YOnDkOnxvIEf0uVyNdWDKHxejHi+qXwCDs\n"
        b"5nkDIXuI+VK3Nrg5uJWJjzWMPouzAPgUx35NLfWiBBq8+G7t0OF6HceDCHJqCFom\n"
        b"Mp6XxJ9btFneFlKCRu2WnBiVH0Vz4q66vsvULCuowcU69+dRRyd46BmuaCjzuqcF\n"
        b"OhlztLEEuRSp16I3+XGVzkU2o8rVZURVc7CZ+JTPa03fgWoU9KG+mR9F93ivPYyI\n"
        b"/AAKKC7xuvj1/k0awl7eKnZOOnh71SnhXM2KVdF3YrLf4FjvkqxOYu9Z6qo+wBq1\n"
        b"3kUBInbKCShMIB5BbzR6LGMCAwEAAQ==\n"
        b"-----END PUBLIC KEY-----"
    )
    return _RAW_PUBLIC_KEY_PEM


class LicenseCrypto:
    """
    RSA-based license signature and verification system.
    """

    @classmethod
    def _get_public_key_pem(cls):
        """Get the public key PEM, reconstructing from obfuscated storage."""
        return _reconstruct_public_key()

    @classmethod
    def verify_license_signature(cls, license_data, signature):
        """
        Verify license signature using RSA.

        Args:
            license_data (dict): License data
            signature (str): Base64-encoded signature

        Returns:
            bool: True if the signature is valid, False otherwise

        Note:
            This cannot be forged without the private key, which resides
            only on the license server.
        """
        try:
            # Downloading a public key from an obfuscated repository
            public_key = serialization.load_pem_public_key(
                cls._get_public_key_pem(),
                backend=default_backend()
            )
            
            # Creating a canonical data form (sorted keys, no spaces)
            # IMPORTANT: separators=(',', ':') without spaces is the format used on the License Server
            canonical_data = json.dumps(license_data, sort_keys=True, separators=(',', ':')).encode('utf-8')
            
            # Signature decoding from Base64 with padding processing
            # Base64 may require padding (=) if the length is not a multiple of 4
            signature_clean = signature.strip()
            
            # Add padding if needed
            missing_padding = len(signature_clean) % 4
            if missing_padding:
                signature_clean += '=' * (4 - missing_padding)
            
            try:
                signature_bytes = base64.b64decode(signature_clean, validate=True)
            except Exception as decode_error:
                logger.error(f"Failed to decode signature from Base64: {str(decode_error)}")
                logger.error(f"Signature length: {len(signature)}, Clean length: {len(signature_clean)}")
                raise ValueError(f"Invalid Base64 signature: {str(decode_error)}")
            
            # Signature verification (PSS with MAX_LENGTH salt - working version)
            public_key.verify(
                signature_bytes,
                canonical_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            logger.info("License signature verification: SUCCESS")
            return True
            
        except Exception as e:
            logger.error(f"License signature verification FAILED: {str(e)}", exc_info=True)
            return False
    
    @classmethod
    def extract_license_data(cls, license_key):
        """
        Extract data from a license key.

        Args:
            license_key (str): License key in BASE64(JSON_DATA).BASE64(SIGNATURE) format

        Returns:
            tuple: (license_data dict, signature str) or (None, None) on error

        Format:
            License key must be in the form: DATA.SIGNATURE
            where DATA = Base64(JSON) and SIGNATURE = Base64(RSA_SIGNATURE)
        """
        try:
            # Splitting the key into two parts
            parts = license_key.split('.')
            
            if len(parts) != 2:
                logger.error(f"Invalid license key format: expected 2 parts, got {len(parts)}")
                return None, None
            
            data_part, signature_part = parts
            
            # Decoding data from Base64
            license_data_json = base64.b64decode(data_part)
            license_data = json.loads(license_data_json.decode('utf-8'))
            
            # Signature is already in Base64, we pass it as is
            signature = signature_part
            
            logger.info(f"License data extracted successfully for company: {license_data.get('company', 'Unknown')}")
            return license_data, signature
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode license JSON data: {str(e)}")
            return None, None
        except Exception as e:
            logger.error(f"Failed to extract license data: {str(e)}")
            return None, None
    
    @classmethod
    def validate_license_key(cls, license_key):
        """
        Full license key validation (extraction + signature verification).

        Args:
            license_key (str): License key

        Returns:
            tuple: (success: bool, license_data: dict or None, error: str or None)
        """
        # Step 1: Data extraction
        license_data, signature = cls.extract_license_data(license_key)
        
        if not license_data or not signature:
            return False, None, "Failed to extract license data"
        
        # Step 2: Verify the signature
        if not cls.verify_license_signature(license_data, signature):
            return False, None, "License signature verification failed"
        
        # Step 3: Check required fields
        required_fields = ['company', 'hardware_id', 'expiration_date', 'max_users', 'modules']
        missing_fields = [field for field in required_fields if field not in license_data]
        
        if missing_fields:
            return False, None, f"Missing required fields: {', '.join(missing_fields)}"
        
        logger.info(f"License validation SUCCESS for company: {license_data.get('company')}")
        return True, license_data, None
    
    @staticmethod
    def generate_rsa_keys():
        """
        Generate an RSA key pair (used ONLY on the license server).

        Returns:
            tuple: (private_key_pem: bytes, public_key_pem: bytes)

        Note:
            This function must be used ONLY on the license server once
            to generate a key pair. The private key is stored on the server;
            the public key is copied into PUBLIC_KEY_PEM above.

        Usage (license server only):
            >>> private_pem, public_pem = LicenseCrypto.generate_rsa_keys()
            >>> # Save private_pem in a secure location on the license server
            >>> # Copy public_pem into PUBLIC_KEY_PEM in this file
        """
        # Private key generation (4096 bits for maximum security)
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        
        # Obtaining a public key
        public_key = private_key.public_key()
        
        # Private key serialization in PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialization of public key in PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem, public_pem


class LicenseKeyFormatter:
    """
    Helper class for formatting license keys.
    """
    
    @staticmethod
    def format_for_display(license_key, chunk_size=4, separator='-'):
        """
        Format a license key for convenient display.

        Args:
            license_key (str): Original license key
            chunk_size (int): Chunk size for splitting
            separator (str): Separator between chunks

        Returns:
            str: Formatted key (e.g. XXXX-XXXX-XXXX-XXXX)

        Note:
            For display only; store the original key.
        """
        # We delete the existing separators
        clean_key = license_key.replace(separator, '')
        
        # Break into chunks
        chunks = [clean_key[i:i+chunk_size] for i in range(0, len(clean_key), chunk_size)]
        
        # Limit for display (first 20 characters)
        display_chunks = chunks[:5]  # 5 chunks of 4 symbols each = 20 symbols
        
        return separator.join(display_chunks) + '...'
    
    @staticmethod
    def normalize_license_key(license_key):
        """
        Normalize a license key (remove spaces, dashes, etc.).

        Args:
            license_key (str): License key with possible separators

        Returns:
            str: Normalized key without separators
        """
        # We remove spaces and hyphens
        return license_key.replace(' ', '').replace('-', '').strip()


# For testing (delete in production)
if __name__ == '__main__':
    # Example of key generation (for demonstration purposes only)
    print("Generating RSA key pair...")
    private_pem, public_pem = LicenseCrypto.generate_rsa_keys()
    
    print("\n=== PRIVATE KEY (зберегти на license server) ===")
    print(private_pem.decode())
    
    print("\n=== PUBLIC KEY (скопіювати в PUBLIC_KEY_PEM) ===")
    print(public_pem.decode())
    
    print("\nIMPORTANT: Приватний ключ має зберігатися ТІЛЬКИ на сервері ліцензій!")
    print("ВАЖЛИВО: Після генерації замініть PUBLIC_KEY_PEM у цьому файлі на згенерований публічний ключ!")

