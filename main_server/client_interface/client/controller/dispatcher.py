import json
from client.constants import GAME_SERVERS_API_ENDPOINT
from client.controller.api_client import get_request
from common.structures import Message, Server


class Dispatcher:
        
    def __pick_server(self, servers_list):
        """
        Balance logic.
        """
        return min(servers_list, key=lambda server: server.connected_users) if servers_list else None
        
    def pick_game_server(self):
        response, error = get_request(GAME_SERVERS_API_ENDPOINT)
        if error:
            return None, error
        
        message = Message(**response)
        if not message.success:
            return None, message.to_dict()
        
        servers = message.data  # Already a list of dicts
        received_servers = [Server.from_dict(server) for server in servers]
        
        picked = self.__pick_server(received_servers)
        if not picked:
            return None, Message.failure('Servers are full').to_dict()
        return picked, None