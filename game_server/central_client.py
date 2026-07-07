"""HTTP client for everything this game server says to the central server.

Every call carries a short-lived Bearer JWT signed with the SHARED_SECRET;
after registration the token also carries this server's assigned id.
"""
import time

import jwt
import requests

from game_server.config import CAPACITY, CENTRAL_URL, SHARED_SECRET
from shared.messages import CAPACITY as CAPACITY_FIELD
from shared.messages import HOST, LOAD, PORT, RESULTS, SERVER_ID

SERVER_TOKEN_TTL = 60


class CentralClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.server_id = None

    def _bearer(self):
        now = int(time.time())
        claims = {'iat': now, 'exp': now + SERVER_TOKEN_TTL}
        if self.server_id is not None:
            claims[SERVER_ID] = self.server_id
        token = jwt.encode(claims, SHARED_SECRET, algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    def register(self, host, port):
        """Announce this server to central; stores the assigned server id."""
        try:
            response = requests.post(f'{self.base_url}/api/servers/register',
                                     json={HOST: host, PORT: port, CAPACITY_FIELD: CAPACITY},
                                     headers=self._bearer(), timeout=5)
            response.raise_for_status()
            self.server_id = response.json()[SERVER_ID]
            return True
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f'[central] registration failed: {e}')
            return False

    def heartbeat(self, load):
        """Report liveness and current load; returns the HTTP status or None."""
        try:
            response = requests.post(f'{self.base_url}/api/servers/heartbeat',
                                     json={LOAD: load},
                                     headers=self._bearer(), timeout=5)
            return response.status_code
        except requests.RequestException:
            return None

    def send_results(self, results):
        try:
            response = requests.post(f'{self.base_url}/api/servers/results',
                                     json={RESULTS: [r.to_dict() for r in results]},
                                     headers=self._bearer(), timeout=5)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f'[central] sending results failed: {e}')
            return False


client = CentralClient(CENTRAL_URL)
