from flask import Blueprint, jsonify, redirect, render_template, request, session

from central_server import db, maintainance
from central_server.config import ADMIN_PASSWORD, ADMIN_USERNAME

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# keeps a player named 'admin' separate from the actual admin
ADMIN_SESSION_KEY = 'admin'


def _is_admin():
    return session.get(ADMIN_SESSION_KEY) is True


@admin_bp.route('/')
def panel():
    if not _is_admin():
        return redirect('/admin/login')
    return render_template('admin.html')


@admin_bp.route('/login', methods=['GET'])
def login_page():
    if _is_admin():
        return redirect('/admin/')
    return render_template('admin_login.html')


@admin_bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return render_template('admin_login.html', error='Wrong username or password'), 401
    session[ADMIN_SESSION_KEY] = True
    return redirect('/admin/')


@admin_bp.route('/logout', methods=['POST'])
def logout():
    session.pop(ADMIN_SESSION_KEY, None)
    return redirect('/admin/login')


@admin_bp.route('/servers')
def servers():
    """Polled by the panel to keep the list of game servers up to date"""
    if not _is_admin():
        return jsonify({'error': 'Admin login required'}), 401
    return jsonify({'servers': db.list_servers()})


@admin_bp.route('/servers/<int:server_id>/maintainance', methods=['POST'])
def start_maintainance(server_id):
    if not _is_admin():
        return jsonify({'error': 'Admin login required'}), 401
    # dispatch stops first: if the call below is lost, the shutdown sender
    # keeps trying
    if not db.set_server_maintainance(server_id):
        return jsonify({'error': 'Unknown game server'}), 404
    server = db.get_server(server_id)
    reached = server is not None and maintainance.send_shutdown(server)
    return jsonify({'success': True, 'reached': reached})
