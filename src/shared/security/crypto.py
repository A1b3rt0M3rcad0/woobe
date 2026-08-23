import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def _derive_key(base_key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    return kdf.derive(base_key.encode())


def hash_password(password: str) -> bytes:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt + key


def verify_password(password: str, stored: bytes) -> bool:
    salt = stored[:16]
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return stored == salt + key


def encrypt_secret(value: str, key: str) -> str:
    salt = os.urandom(16)
    derived = _derive_key(key, salt)
    f = Fernet(base64.urlsafe_b64encode(derived))
    token = f.encrypt(value.encode())
    return salt.hex() + ":" + token.decode()


def decrypt_secret(encrypted: str, key: str) -> str:
    parts = encrypted.split(":", 1)
    salt = bytes.fromhex(parts[0])
    token = parts[1].encode()
    derived = _derive_key(key, salt)
    f = Fernet(base64.urlsafe_b64encode(derived))
    return f.decrypt(token).decode()
