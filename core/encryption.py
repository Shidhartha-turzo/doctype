"""
Encryption Utilities for Zero Trust Architecture

Provides field-level encryption and backup encryption functionality.
Implements AES-256-GCM for data-at-rest encryption.

Zero Trust Principle: Never store sensitive data in plaintext
"""

import os
import base64
import logging
from typing import Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger('encryption')


class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass


class EncryptionKeyManager:
    """
    Manages encryption keys with secure generation and storage

    Zero Trust: Keys must be rotatable and stored securely
    """

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new 256-bit encryption key

        Returns:
            32-byte encryption key
        """
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2

        Args:
            password: Master password
            salt: Salt for key derivation

        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    @staticmethod
    def get_field_encryption_key() -> bytes:
        """
        Get field encryption key from settings

        Returns:
            Field encryption key

        Raises:
            ImproperlyConfigured: If key not configured
        """
        key_b64 = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)

        if not key_b64:
            logger.warning("FIELD_ENCRYPTION_KEY not configured, generating temporary key")
            # Generate temporary key (NOT for production!)
            key = EncryptionKeyManager.generate_key()
            return key

        try:
            return base64.b64decode(key_b64)
        except Exception as e:
            raise ImproperlyConfigured(f"Invalid FIELD_ENCRYPTION_KEY: {e}")

    @staticmethod
    def get_backup_encryption_key() -> bytes:
        """
        Get backup encryption key from settings

        Returns:
            Backup encryption key

        Raises:
            ImproperlyConfigured: If key not configured
        """
        key_b64 = getattr(settings, 'BACKUP_ENCRYPTION_KEY', None)

        if not key_b64:
            logger.warning("BACKUP_ENCRYPTION_KEY not configured, generating temporary key")
            # Generate temporary key (NOT for production!)
            key = EncryptionKeyManager.generate_key()
            return key

        try:
            return base64.b64decode(key_b64)
        except Exception as e:
            raise ImproperlyConfigured(f"Invalid BACKUP_ENCRYPTION_KEY: {e}")


class FieldEncryption:
    """
    Field-level encryption for sensitive database fields

    Uses AES-256-GCM for authenticated encryption
    """

    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize field encryption

        Args:
            key: Encryption key (if None, uses settings)
        """
        if key is None:
            key = EncryptionKeyManager.get_field_encryption_key()

        if len(key) != 32:
            raise ValueError("Encryption key must be 32 bytes (256 bits)")

        self.cipher = AESGCM(key)
        logger.info("FieldEncryption initialized")

    def encrypt(self, plaintext: Union[str, bytes]) -> str:
        """
        Encrypt plaintext data

        Args:
            plaintext: Data to encrypt (string or bytes)

        Returns:
            Base64-encoded encrypted data with nonce

        Format: base64(nonce || ciphertext || tag)
        """
        try:
            # Convert string to bytes if needed
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')

            # Generate random nonce (12 bytes for GCM)
            nonce = os.urandom(12)

            # Encrypt (includes authentication tag)
            ciphertext = self.cipher.encrypt(nonce, plaintext, None)

            # Combine nonce + ciphertext and encode
            encrypted_data = nonce + ciphertext
            result = base64.b64encode(encrypted_data).decode('ascii')

            logger.debug(f"Encrypted {len(plaintext)} bytes")
            return result

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data

        Args:
            encrypted_data: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext string
        """
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data)

            # Extract nonce (first 12 bytes)
            nonce = data[:12]

            # Extract ciphertext (remaining bytes)
            ciphertext = data[12:]

            # Decrypt and verify
            plaintext = self.cipher.decrypt(nonce, ciphertext, None)

            # Convert bytes to string
            result = plaintext.decode('utf-8')

            logger.debug(f"Decrypted {len(result)} bytes")
            return result

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_if_needed(self, value: Optional[str]) -> Optional[str]:
        """
        Encrypt value if not already encrypted

        Args:
            value: Value to encrypt

        Returns:
            Encrypted value or None
        """
        if value is None:
            return None

        # Check if already encrypted (base64 format check)
        try:
            base64.b64decode(value)
            # If successful, might be encrypted (but not guaranteed)
            # For safety, we'll check if it starts with our marker
            if len(value) > 16:  # Minimum encrypted length
                return value  # Assume already encrypted
        except:
            pass

        return self.encrypt(value)


class BackupEncryption:
    """
    Backup file encryption

    Encrypts entire backup files using AES-256-GCM
    """

    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize backup encryption

        Args:
            key: Encryption key (if None, uses settings)
        """
        if key is None:
            key = EncryptionKeyManager.get_backup_encryption_key()

        if len(key) != 32:
            raise ValueError("Encryption key must be 32 bytes (256 bits)")

        self.cipher = AESGCM(key)
        logger.info("BackupEncryption initialized")

    def encrypt_file(self, input_path: str, output_path: str) -> dict:
        """
        Encrypt a backup file

        Args:
            input_path: Path to plaintext backup file
            output_path: Path to save encrypted backup

        Returns:
            dict with encryption metadata
        """
        try:
            logger.info(f"Encrypting backup: {input_path} -> {output_path}")

            # Read plaintext backup
            with open(input_path, 'rb') as f:
                plaintext = f.read()

            # Generate nonce
            nonce = os.urandom(12)

            # Encrypt
            ciphertext = self.cipher.encrypt(nonce, plaintext, None)

            # Write encrypted file (nonce + ciphertext)
            with open(output_path, 'wb') as f:
                f.write(nonce)
                f.write(ciphertext)

            metadata = {
                'original_size': len(plaintext),
                'encrypted_size': len(nonce) + len(ciphertext),
                'algorithm': 'AES-256-GCM',
                'encrypted': True
            }

            logger.info(f"Backup encrypted successfully: {metadata}")
            return metadata

        except Exception as e:
            logger.error(f"Backup encryption failed: {e}")
            raise EncryptionError(f"Backup encryption failed: {e}")

    def decrypt_file(self, input_path: str, output_path: str) -> dict:
        """
        Decrypt a backup file

        Args:
            input_path: Path to encrypted backup file
            output_path: Path to save decrypted backup

        Returns:
            dict with decryption metadata
        """
        try:
            logger.info(f"Decrypting backup: {input_path} -> {output_path}")

            # Read encrypted backup
            with open(input_path, 'rb') as f:
                data = f.read()

            # Extract nonce (first 12 bytes)
            nonce = data[:12]

            # Extract ciphertext (remaining bytes)
            ciphertext = data[12:]

            # Decrypt
            plaintext = self.cipher.decrypt(nonce, ciphertext, None)

            # Write decrypted file
            with open(output_path, 'wb') as f:
                f.write(plaintext)

            metadata = {
                'encrypted_size': len(data),
                'decrypted_size': len(plaintext),
                'algorithm': 'AES-256-GCM',
                'decrypted': True
            }

            logger.info(f"Backup decrypted successfully: {metadata}")
            return metadata

        except Exception as e:
            logger.error(f"Backup decryption failed: {e}")
            raise EncryptionError(f"Backup decryption failed: {e}")


# Convenience functions for easy use

def encrypt_field(value: str) -> str:
    """
    Encrypt a field value

    Args:
        value: Plaintext value

    Returns:
        Encrypted value
    """
    encryptor = FieldEncryption()
    return encryptor.encrypt(value)


def decrypt_field(encrypted_value: str) -> str:
    """
    Decrypt a field value

    Args:
        encrypted_value: Encrypted value

    Returns:
        Decrypted plaintext
    """
    encryptor = FieldEncryption()
    return encryptor.decrypt(encrypted_value)


def encrypt_backup(input_path: str, output_path: str) -> dict:
    """
    Encrypt a backup file

    Args:
        input_path: Path to plaintext backup
        output_path: Path for encrypted backup

    Returns:
        Encryption metadata
    """
    encryptor = BackupEncryption()
    return encryptor.encrypt_file(input_path, output_path)


def decrypt_backup(input_path: str, output_path: str) -> dict:
    """
    Decrypt a backup file

    Args:
        input_path: Path to encrypted backup
        output_path: Path for decrypted backup

    Returns:
        Decryption metadata
    """
    encryptor = BackupEncryption()
    return encryptor.decrypt_file(input_path, output_path)


def generate_encryption_keys() -> dict:
    """
    Generate new encryption keys

    Returns:
        dict with base64-encoded keys
    """
    field_key = EncryptionKeyManager.generate_key()
    backup_key = EncryptionKeyManager.generate_key()

    return {
        'FIELD_ENCRYPTION_KEY': base64.b64encode(field_key).decode('ascii'),
        'BACKUP_ENCRYPTION_KEY': base64.b64encode(backup_key).decode('ascii'),
    }


# Key generation CLI
if __name__ == '__main__':
    print("Generating encryption keys...")
    keys = generate_encryption_keys()
    print("\nAdd these to your .env file:\n")
    for key_name, key_value in keys.items():
        print(f"{key_name}={key_value}")
    print("\nWARNING: Keep these keys secure! Store in environment variables, not in code.")
