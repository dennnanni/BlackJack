# import requests

# class CentralServerClient:
#     def __init__(self, base_url):
#         self.base_url = base_url

#     def register_game_server(self, server_id, host, port):
#         try:
#             response = requests.post(f"{self.base_url}/register", json={
#                 "server_id": server_id,
#                 "host": host,
#                 "port": port
#             }, timeout=5)
#             response.raise_for_status()
#             return response.json()
#         except requests.RequestException as e:
#             print(f"[!] Errore registrazione server: {e}")
#             return None

#     def send_results(self, results):
#         try:
#             response = requests.post(f"{self.base_url}/results", json={"results": results}, timeout=5)
#             response.raise_for_status()
#         except requests.RequestException as e:
#             print(f"[!] Errore invio risultati: {e}")

#     def update_user_list(self, server_id, users):
#         try:
#             response = requests.post(f"{self.base_url}/users", json={
#                 "server_id": server_id,
#                 "users": users
#             }, timeout=5)
#             response.raise_for_status()
#         except requests.RequestException as e:
#             print(f"[!] Errore aggiornamento lista utenti: {e}")

import requests
from src.encryption import encrypt_with_key


class CentralServerAPI:
    def __init__(self, base_url: str, shared_secret: bytes, server_id):
        self.base_url = base_url
        self.new_key = shared_secret
        self.server_id = server_id

    def register_game_server(self, key: bytes, host: str, port: int):
        payload = {
            "server_id": self.server_id,
            "host": host,
            "port": port,
            "key": self.new_key
        }

        try:
            encrypted_data = encrypt_with_key(payload, key)
            response = requests.post(
                f"{self.base_url}/register",
                json={"data": encrypted_data},
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"[!] Errore registrazione server: {e}")
            return None

    def send_results(self, results: list):
        results_payload = [r.to_dict() for r in results]
        payload = {"results": results_payload}
        try:
            encrypted_data = encrypt_with_key(payload, self.new_key)
            response = requests.post(
                f"{self.base_url}/results",
                json={"data": encrypted_data},
                timeout=5
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Errore invio risultati: {e}")

    def update_user_list(self, users: list):
        payload = {
            "server_id": self.server_id,
            "users": users
        }
        try:
            encrypted_data = encrypt_with_key(payload, self.new_key)
            response = requests.post(
                f"{self.base_url}/users",
                json={"data": encrypted_data},
                timeout=5
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Errore aggiornamento lista utenti: {e}")
