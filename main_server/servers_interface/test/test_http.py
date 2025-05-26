import json
import os
from common.response_fields import ENCRYPTED, ERROR
from common.structures import Result, Server
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import jwt
import requests

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET').encode()
if not SHARED_SECRET:
    raise ValueError("SHARED_SECRET environment variable not set")
fernet_shared_secret = Fernet(SHARED_SECRET)

TEST_KEY = os.getenv('TEST_KEY')
fernet = Fernet(TEST_KEY.encode())

def test_registration():
    
    test_data = Server("127.0.0.1", 7000, TEST_KEY).to_dict()
    
    # Encrypt the test data
    encrypted_data = fernet_shared_secret.encrypt(json.dumps(test_data).encode())
    
    response = requests.post("http://localhost:5002/register", data=encrypted_data)
    print(f"Response status code: {response.status_code}")
    
    content = response.json()
    
    assert content.get(ENCRYPTED) is not None, content.get(ERROR)
    data = fernet.decrypt(content.get(ENCRYPTED).encode()).decode()
    data = json.loads(data)
    assert test_data == data
    
    
def test_publish_results():
    server_id = 18
    test_data = [
        Result('den', 100, 100).to_dict(),
        Result('ago', 200, 300).to_dict(),
        Result('nicola', -25, 25).to_dict()
    ]
    
    token = {
        'server_id': server_id,
        'results': test_data
    }
        
    jwt_token = jwt.encode(token, TEST_KEY.encode(), algorithm='HS256')
    headers = {
        'X-Server-ID': str(server_id),
    }
    
    response = requests.post("http://localhost:5002/result", json={'token': jwt_token}, headers=headers)
    assert response.status_code == 200, response.text