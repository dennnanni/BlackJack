from src import create_app, socketio
from src.config.settings import SERVER_HOST, SERVER_PORT

def main():
    app = create_app()
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, debug=True, allow_unsafe_werkzeug=True)
    
if __name__ == "__main__":
    main()