"""Objects shared by the whole process."""
import threading
from uuid import uuid4

from flask_socketio import SocketIO

from game_server.config import OUTBOX_PATH
from game_server.outbox import Outbox

socketio = SocketIO()
outbox = Outbox(OUTBOX_PATH)

# Changes on every start. A restart loses every table
BOOT_ID = uuid4().hex

# Set when central shuts this server down: no new round starts, and each table
# sends its players back to central once its round is over
closing = threading.Event()
