"""Encryption at rest for stored secrets (Sonarr API keys, Apprise URLs)."""

from cryptography.fernet import Fernet, InvalidToken

_VISIBLE_TAIL = 4
_MIN_LENGTH_FOR_TAIL = 12


class SecretDecryptError(RuntimeError):
    """A stored secret cannot be decrypted, usually because FINALARR_SECRET_KEY changed."""


class SecretBox:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except (InvalidToken, ValueError):
            raise SecretDecryptError(
                "Stored secret cannot be decrypted; was FINALARR_SECRET_KEY changed?"
            ) from None


def mask(value: str | None) -> str:
    """Show at most the last four characters, and only of long values."""
    if not value:
        return ""
    if len(value) < _MIN_LENGTH_FOR_TAIL:
        return "***"
    return "***" + value[-_VISIBLE_TAIL:]
