from flask import Blueprint, render_template

client_bp = Blueprint('client_interface', __name__)

@client_bp.route('/user/<username>')
def index(username):
    return render_template('home.html', username=username)

@client_bp.route('/')
@client_bp.route('/login')
def login():
    return render_template('access.html', login=True)

@client_bp.route('/register')
def register():
    return render_template('access.html', register=True)
