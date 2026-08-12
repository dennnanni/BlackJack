from client.controller.web_controller import client_bp
from client.controller.servers_controller import servers_bp

def register_routes(app):
    app.register_blueprint(client_bp)
    app.register_blueprint(servers_bp, url_prefix='/api/servers')