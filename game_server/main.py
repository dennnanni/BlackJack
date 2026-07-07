from game_server.app import create_app, socketio
from game_server.config import SERVER_PORT


def main():
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=SERVER_PORT, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
