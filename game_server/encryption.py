import json
from typing import Union
from cryptography.fernet import Fernet

def encrypt_with_key(payload: dict, key: bytes) -> str:
    fernet = Fernet(key)
    return fernet.encrypt(json.dumps(payload).encode()).decode()

def decrypt_with_key(encrypted_data: str, key: bytes) -> str:
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_data.encode()).decode()
