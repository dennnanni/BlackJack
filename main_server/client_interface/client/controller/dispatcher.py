from client.constants import GAME_SERVERS_API_ENDPOINT
from common.http_requests import get_request
from common.response_fields import DATA, ERROR
from common.structures import RegisteredServer
from servers import DATABASE_URL


class Dispatcher:
        
    def __pick_server(self, servers_list):
        """
        Balance logic.
        """
        return min(servers_list, key=lambda server: server.connected_users) if servers_list else None
        
    def pick_game_server(self):
        response = get_request(DATABASE_URL, GAME_SERVERS_API_ENDPOINT)
        if response.get(ERROR):
            return None, response.get(ERROR)
        
        servers = response.get(DATA)
        if not servers:
            return None, 'No servers available'
        
        received_servers = [RegisteredServer.from_dict(server) for server in servers]
        
        picked = self.__pick_server(received_servers)
        if not picked:
            return None, 'Servers are full'
        return picked, None