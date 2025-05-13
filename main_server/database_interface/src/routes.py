from src.controller.database_controller import database_bp

def register_routes(app):
    app.register_blueprint(database_bp)
    