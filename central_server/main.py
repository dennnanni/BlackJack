from central_server.app import create_app
from central_server.config import CENTRAL_PORT


def main():
    app = create_app()
    app.run(host='0.0.0.0', port=CENTRAL_PORT, threaded=True)


if __name__ == '__main__':
    main()
