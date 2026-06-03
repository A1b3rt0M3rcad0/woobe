import pytest

from shared.infra.crypto import hash_password, verify_password, encrypt_secret, decrypt_secret


class TestPasswordHashing:
    def test_hash_and_verify_round_trip(self):
        password = "my-secure-password-123!"
        hashed = hash_password(password)
        assert isinstance(hashed, bytes)
        assert verify_password(password, hashed) is True

    def test_wrong_password_returns_false(self):
        password = "correct-password"
        wrong = "wrong-password"
        hashed = hash_password(password)
        assert verify_password(wrong, hashed) is False

    def test_different_hashes_for_same_password(self):
        password = "same-password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("x", hashed) is False


class TestSecretEncryption:
    def test_encrypt_and_decrypt_round_trip(self):
        secret = "sk-abc123-secret-value"
        key = "my-encryption-key"
        encrypted = encrypt_secret(secret, key)
        assert isinstance(encrypted, str)
        assert ":" in encrypted
        decrypted = decrypt_secret(encrypted, key)
        assert decrypted == secret

    def test_different_keys_produce_different_ciphertexts(self):
        secret = "same-value"
        enc1 = encrypt_secret(secret, "key-a")
        enc2 = encrypt_secret(secret, "key-b")
        assert enc1 != enc2

    def test_decrypt_with_wrong_key_raises_error(self):
        secret = "my-secret"
        key = "correct-key"
        wrong_key = "wrong-key"
        encrypted = encrypt_secret(secret, key)
        with pytest.raises(Exception):
            decrypt_secret(encrypted, wrong_key)

    def test_decrypt_with_tampered_ciphertext_raises_error(self):
        secret = "my-secret"
        key = "my-key"
        encrypted = encrypt_secret(secret, key)
        tampered = encrypted[:-1] + ("0" if encrypted[-1] == "1" else "1")
        with pytest.raises(Exception):
            decrypt_secret(tampered, key)
