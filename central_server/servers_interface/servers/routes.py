from servers.controller.servers_controller import servers_bp

def register_routes(app):
    app.register_blueprint(servers_bp)