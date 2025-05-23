import json
import os
from urllib import response
from common.response_fields import ENCRYPTED, ERROR
from common.structures import Server
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import requests

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET').encode()
if not SHARED_SECRET:
    raise ValueError("SHARED_SECRET environment variable not set")
fernet_shared_secret = Fernet(SHARED_SECRET)

key = Fernet.generate_key()
fernet = Fernet(key)

def test_registration():
    test_data = Server("127.0.0.1", 7000, key.decode()).to_dict()
    
    # Encrypt the test data
    encrypted_data = fernet_shared_secret.encrypt(json.dumps(test_data).encode())
    
    response = requests.post("http://localhost:5002/register", data=encrypted_data)
    
    content = response.json()
    
    assert content.get(ENCRYPTED) is not None, content.get(ERROR)
    data = fernet.decrypt(content.get(ENCRYPTED).encode()).decode()
    data = json.loads(data)
    assert test_data == data
    
    