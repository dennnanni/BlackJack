import json
from cryptography.fernet import Fernet

def get_fernet(key: bytes) -> Fernet:
    return Fernet(key)

def encrypt_with_key(data: dict, key: bytes) -> str:
    fernet = get_fernet(key)
    json_data = json.dumps(data).encode()
    encrypted = fernet.encrypt(json_data)
    return encrypted.decode()

def decrypt_with_key(token: str, key: bytes) -> dict:
    fernet = get_fernet(key)
    decrypted = fernet.decrypt(token.encode())
    return json.loads(decrypted.decode())
