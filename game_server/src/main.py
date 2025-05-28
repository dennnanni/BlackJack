from src import create_app, socketio
from src.config.settings import SERVER_HOST, SERVER_PORT

def main():
    app = create_app()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    main()
