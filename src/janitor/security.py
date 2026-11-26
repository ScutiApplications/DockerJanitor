"""Password hashing, secret encryption and the one-time setup code."""
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

MAX_SETUP_TRIES = 5


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return f"{salt.hex()}${_scrypt(password, salt).hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, _, digest = stored.partition("$")
    return hmac.compare_digest(_scrypt(password, bytes.fromhex(salt)).hex(), digest)


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)


class SecretBox:
    """Encrypts secrets with a key file kept apart from the database."""

    def __init__(self, key_file: Path):
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if not key_file.exists():
            descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(Fernet.generate_key())
        self._fernet = Fernet(key_file.read_bytes())

    def seal(self, text: str) -> str:
        return self._fernet.encrypt(text.encode()).decode()

    def open(self, token: str) -> str:
        """Raises ValueError when the key does not match the stored secret."""
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as error:
            raise ValueError("stored SMTP password cannot be decrypted; enter it again") from error


class SetupCode:
    """A random code shown only in the container log; it locks after a few wrong tries."""

    def __init__(self):
        self.code = secrets.token_hex(6)
        self.tries_left = MAX_SETUP_TRIES

    def accepts(self, attempt: str) -> bool:
        if self.tries_left <= 0:
            return False
        if hmac.compare_digest(attempt.strip().encode(), self.code.encode()):
            return True
        self.tries_left -= 1
        return False
