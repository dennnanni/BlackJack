from central_server.app import create_app, socketio
from central_server.config import CENTRAL_PORT


def main():
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=CENTRAL_PORT, debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
