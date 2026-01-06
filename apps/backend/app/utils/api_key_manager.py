# backend/app/utils/api_key_manager.py
from cryptography.fernet import Fernet


class APIKeyManager:
    """Encrypt/decrypt external API keys (Google Maps, Walk Score, etc.)"""

    def __init__(self, encryption_key: str):
        self.cipher = Fernet(encryption_key.encode())

    def encrypt_api_key(self, api_key: str) -> str:
        return self.cipher.encrypt(api_key.encode()).decode()

    def decrypt_api_key(self, encrypted_key: str) -> str:
        return self.cipher.decrypt(encrypted_key.encode()).decode()
