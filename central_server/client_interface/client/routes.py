from client.controller.web_controller import client_bp

def register_routes(app):
    app.register_blueprint(client_bp)