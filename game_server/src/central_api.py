import json
import requests
from src.encryption import encrypt_with_key, decrypt_with_key


class CentralServerAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def register_game_server(self, host: str, port: int, shared_key, new_key):
        self.new_key = new_key
        payload = {
            "ip": host,
            "port": port,
            "key": self.new_key.decode()
        }

        try:
            encrypted_data = encrypt_with_key(payload, shared_key)
            response = requests.post(
                f"{self.base_url}/register",
                json={"encrypted": encrypted_data},
                timeout=5
            )
            response.raise_for_status()
            encrypted_response = response.json().get("encrypted")
            if encrypted_response:
                decrypted_data = json.loads(decrypt_with_key(encrypted_response, self.new_key))
                self.server_id = decrypted_data.get("server_id")
            else:
                raise ValueError("No data field in response")
            
            return True
        except requests.RequestException as e:
            print(f"[!] Errore registrazione server: {e}")
            if e.response is not None:
                print(f"[!] Codice risposta: {e.response.status_code}")
                print(f"[!] Contenuto risposta: {e.response.text}")
            return False

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
