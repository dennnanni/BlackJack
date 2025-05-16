from flask import Blueprint, render_template

client_bp = Blueprint('client_interface', __name__)

@client_bp.route('/user/<username>')
def index(username):
    return render_template('home.html', username=username)

@client_bp.route('/login')
def login():
    return render_template('login.html')
