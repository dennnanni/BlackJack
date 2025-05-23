import json
from common.http_requests import post_request
from common.structures import Message, Server
from flask import Blueprint, request
from servers import DATABASE_URL, fernet_shared_secret
from servers.constants import REGISTER_NEW_SERVER_API_ENDPOINT
from cryptography.fernet import Fernet

servers_bp = Blueprint("servers", __name__)

@servers_bp.route("/register", methods=["POST"])
def index():
    data = request.get_data()
    if not data:
        return Message.failure("No data provided").to_dict()
    
    # decrypt the message with the shared secret
    cleartext = fernet_shared_secret.decrypt(data).decode()
    
    print(f"Decrypted data: {cleartext}")
    
    try:
        dict = json.loads(cleartext)
        # parse the message
        server = Server(**dict)
    except Exception as e:
        return Message.failure(f'{e}').to_dict()
    
    fernet_private = Fernet(server.key.encode())
    server.key = fernet_shared_secret.encrypt(server.key.encode()).decode()
    
    # register the server in the database
    result, error = post_request(DATABASE_URL, REGISTER_NEW_SERVER_API_ENDPOINT, server.to_dict())
    if error:
        return error
    
    encrypted_data = fernet_private.encrypt(cleartext.encode()).decode()
    print(f"Original data: {data}")
    print(f"Encrypted data: {encrypted_data}")
    
    # success message contains data sent from the server encrypted with its key for validity
    return Message.success("Server registered successfully", data=encrypted_data).to_dict()