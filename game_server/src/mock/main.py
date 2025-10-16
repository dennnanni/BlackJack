from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/register', methods=['POST'])
def register():
    print("✅ Ricevuta registrazione dal Game Server!")
    return jsonify({"status": "ok", "id": "mock-server-1"}), 200

def main():
    app.run(host='0.0.0.0', port=5001)
