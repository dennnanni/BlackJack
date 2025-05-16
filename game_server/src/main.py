# from src import create_app, socketio

    
# def main():
#     app = create_app()
#     socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
    
# if __name__ == "__main__":
#     main()
    
from src import create_app, socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5002, debug=True, allow_unsafe_werkzeug=True)
