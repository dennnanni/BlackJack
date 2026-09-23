"""HTTP client for everything this game server says to the central server.

Every call carries a short-lived Bearer JWT signed with the SHARED_SECRET;
after registration the token also carries this server's assigned id.
If the server is dead, the registration will also carry the last server id.
"""
import time

import jwt
import requests

from game_server.config import (CAPACITY, CENTRAL_URLS, LEASE_TIMEOUT,
                                SHARED_SECRET)
from shared.messages import CAPACITY as CAPACITY_FIELD
from shared.messages import (BUY_INS, HOST, PLAYERS, PORT, RESULTS, ROUND_ID,
                             SERVER_ID, SETTLED, TYP, TYP_SERVER)

SERVER_TOKEN_TTL = 60


class CentralClient:
    def __init__(self, urls):
        self.urls = urls
        self._current = 0   # the replica that answered last
        self.server_id = None
        self._last_contact = time.monotonic()

    def lease_valid(self):
        """True if central answered a register or heartbeat in the last
        LEASE_TIMEOUT seconds. While it is False the tables start no new rounds"""
        return time.monotonic() - self._last_contact < LEASE_TIMEOUT

    def _bearer(self):
        now = int(time.time())
        claims = {TYP: TYP_SERVER, 'iat': now, 'exp': now + SERVER_TOKEN_TTL}
        if self.server_id is not None:
            claims[SERVER_ID] = self.server_id
        token = jwt.encode(claims, SHARED_SECRET, algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    def _post(self, path, body):
        """POST to the replica that answered last. If the replica does not 
        answer, retries on other replicas."""
        error = None
        for _ in range(len(self.urls)):
            url = self.urls[self._current]
            try:
                response = requests.post(f'{url}{path}', json=body,
                                         headers=self._bearer(), timeout=5)
                if response.status_code < 500:
                    return response
                error = requests.HTTPError(f'{response.status_code} from {url}',
                                           response=response)
            except requests.RequestException as e:
                error = e
            # handles overflow of index
            self._current = (self._current + 1) % len(self.urls)
        raise error

    def register(self, host, port):
        """Announce this server to central; stores the assigned server id."""
        try:
            response = self._post('/api/servers/register',
                                  {HOST: host, PORT: port, CAPACITY_FIELD: CAPACITY})
            response.raise_for_status()
            self.server_id = response.json()[SERVER_ID]
            self._last_contact = time.monotonic()
            return True
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f'[central] registration failed: {e}')
            return False

    def heartbeat(self, players):
        try:
            response = self._post('/api/servers/heartbeat', {PLAYERS: players})
            if response.ok:
                # Only a 200 renews the lease. A 404 means central answered but
                # no longer holds our players' seats, which is just as bad as
                # not reaching it.
                self._last_contact = time.monotonic()
            return response.status_code
        except requests.RequestException:
            return None

    def send_results(self, round_id, results):
        """Deliver one round's results; True only when central ACKed them."""
        try:
            response = self._post('/api/servers/results',
                                  {ROUND_ID: round_id,
                                   RESULTS: [r.to_dict() for r in results]})
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f'[central] sending results for round {round_id} failed: {e}')
            return False

    def close_buy_ins(self, buy_in_ids):
        """Tell central these players left, so it hands what is left of their
        buy-ins back to their balance. Returns the ids central settled, or
        None when it did not answer."""
        try:
            response = self._post('/api/servers/leave', {BUY_INS: list(buy_in_ids)})
            response.raise_for_status()
            return response.json()[SETTLED]
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f'[central] closing buy ins {buy_in_ids} failed: {e}')
            return None


client = CentralClient(CENTRAL_URLS)
