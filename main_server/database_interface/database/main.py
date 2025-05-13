from database import create_app, socketio


def main():
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

    
if __name__ == "__main__":
    main()