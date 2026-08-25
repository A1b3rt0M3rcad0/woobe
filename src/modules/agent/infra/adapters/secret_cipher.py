from __future__ import annotations

from shared.infra.crypto import decrypt_secret, encrypt_secret

from modules.agent.application.interfaces.ports import SecretCipherPort


class SecretCipherAdapter(SecretCipherPort):

    def __init__(self, encryption_key: str | None = None) -> None:
        from shared.infra.config import Settings
        self._encryption_key = encryption_key or Settings().encryption_key

    async def encrypt(self, plaintext: str) -> str:
        return encrypt_secret(plaintext, self._encryption_key)

    async def decrypt(self, ciphertext: str) -> str:
        return decrypt_secret(ciphertext, self._encryption_key)
