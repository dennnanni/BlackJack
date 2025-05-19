from client.controller.routes_controller import login_user, register_user
from flask import Blueprint, redirect, render_template, request, session
from flask_login import current_user, login_required

client_bp = Blueprint('client_interface', __name__)

@client_bp.route('/user/<username>')
@login_required
def index(username):
    return render_template('home.html', username=username)

@client_bp.route('/')
@client_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(f'/user/{current_user.username}')
    return render_template('access.html', login=True)

@client_bp.route('/register', methods=['GET'])
def register():
    return render_template('access.html', register=True)


## POST ROUTES

@client_bp.route('/login', methods=['POST'])
def login_post():
    message = login_user(request.form.get('username'), request.form.get('password'))
    return redirect(message['redirect']) if message['success'] else render_template('access.html', error=message['message'])

@client_bp.route('/register', methods=['POST'])
def register_post():
    message = register_user(request.form.get('username'), request.form.get('password'))
    return redirect(message['redirect']) if message['success'] else render_template('access.html', error=message['message'])

@client_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect('/login')