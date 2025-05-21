from database.controller.users_database_controller import users_routes_bp
from database.controller.servers_database_controller import servers_routes_bp

def register_routes(app):
    app.register_blueprint(servers_routes_bp, url_prefix='/servers')
    app.register_blueprint(users_routes_bp, url_prefix='/users')
    