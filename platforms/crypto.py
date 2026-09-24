"""Symmetric encryption for stored credentials using Fernet (AES-128-CBC + HMAC)."""
import os

_UNSET = object()
_cipher = _UNSET


def _get_cipher():
    global _cipher
    if _cipher is not _UNSET:
        return _cipher
    key = os.environ.get('CREDENTIALS_KEY', '').strip()
    if not key:
        _cipher = None
        return None
    try:
        from cryptography.fernet import Fernet
        _cipher = Fernet(key.encode())
    except Exception:
        _cipher = None
    return _cipher


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ''
    cipher = _get_cipher()
    if cipher is None:
        return plaintext
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ''
    cipher = _get_cipher()
    if cipher is None:
        return ciphertext
    try:
        return cipher.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ''


def encryption_active() -> bool:
    return _get_cipher() is not None
