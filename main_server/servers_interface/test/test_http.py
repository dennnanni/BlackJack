import json
import os
from urllib import response
from common.structures import Message, Server
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
    
    message = Message(**response.json())
    assert message.success, message.message
    assert message.data is not None, "No data in response"
    data = fernet.decrypt(message.data.encode()).decode()
    data = json.loads(data)
    assert test_data == data
    
    