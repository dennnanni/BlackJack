from common.structures import ServerLoad
from database.model.database_actions import get_servers_with_user_count


class Dispatcher:

    def __pick_server(self, servers_list):
        """
        Balance logic.
        """
        return min(servers_list, key=lambda server: server.connected_users) if servers_list else None

    def pick_game_server(self):
        servers = get_servers_with_user_count()
        if not servers:
            return None, 'No servers available'

        received_servers = [ServerLoad.from_tuple(server) for server in servers]

        picked = self.__pick_server(received_servers)
        if not picked:
            return None, 'Servers are full'
        return picked, None
