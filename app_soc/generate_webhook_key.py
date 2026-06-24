#!/usr/bin/env python3
"""
Script to generate a new webhook encryption key for SecBoard
"""

from cryptography.fernet import Fernet

def generate_webhook_key():
    """Generate a new Fernet encryption key for webhook authentication data"""
    key = Fernet.generate_key()
    print("=" * 60)
    print("🔐 NEW WEBHOOK ENCRYPTION KEY GENERATED")
    print("=" * 60)
    print(f"Key: {key.decode()}")
    print("=" * 60)
    print("📝 INSTRUCTIONS:")
    print("1. Copy the key above")
    print("2. Open SecBoard/SecBoard/credential.py")
    print("3. Replace 'your-webhook-encryption-key-here' with the new key")
    print("4. Save the file")
    print("=" * 60)
    print("⚠️  IMPORTANT:")
    print("- Keep this key secure and never commit it to version control")
    print("- If you lose this key, all encrypted webhook auth data will be lost")
    print("- Generate a new key for each environment (dev, staging, production)")
    print("=" * 60)

if __name__ == "__main__":
    generate_webhook_key()
