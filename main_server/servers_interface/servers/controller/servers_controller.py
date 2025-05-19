from flask import Blueprint

servers_bp = Blueprint("servers", __name__)

@servers_bp.route("/")
def index():
    return "This is the servers interface."