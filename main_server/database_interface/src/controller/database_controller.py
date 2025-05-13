from flask import Blueprint

database_bp = Blueprint('database', __name__)

@database_bp.route('/', methods=['GET', 'POST'])
def index():
    raise NotImplementedError("This route is not implemented yet.")
