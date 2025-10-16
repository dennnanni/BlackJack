import socketio
import jwt
import time
import random

# Configurazioni
SERVER_URL = 'http://game_server:5000'
SHARED_SECRET = 'ZPYxpWnB_Uv9QY7dJgx2xr_7R38aXEDWzxQdzUHH4W0'  # deve essere uguale a quella del server
USERNAME = "mock_user"
BALANCE = 1000

# Creiamo un token JWT finto (con payload username)
def create_jwt(username):
    payload = {"username": username}
    token = jwt.encode(payload, SHARED_SECRET, algorithm="HS256")
    return token

sio = socketio.Client()
token = create_jwt(USERNAME)
hand = []


@sio.event
def connect():
    print("[✔] Connesso al game server.")
    sio.emit("join", {"username": USERNAME, "balance": BALANCE})

@sio.event
def disconnect():
    print("[✘] Disconnesso dal game server.")

@sio.on("joined")
def on_joined(data):
    print(f"[●] Assegnato al tavolo {data['table_id']} | Player: {data['is_player']}")

@sio.on("initial_cards")
def on_initial_cards(data):
    global hand
    print("[🂠] Carte iniziali ricevute.")
    hand = data["hands"][USERNAME]
    print(" - La mia mano:", hand)
    time.sleep(1)
    place_bet()

@sio.on("bet")
def on_bet_request(_):
    print("[💰] Richiesta puntata ricevuta.")
    place_bet()

@sio.on("bet_confirmed")
def on_bet_confirmed(data):
    print(f"[✔] Puntata confermata: {data['amount']} da {data['user']}")

@sio.on("card_drawn")
def on_card_drawn(data):
    global hand
    if data["user"] == USERNAME:
        print(f"[🂡] Carta pescata: {data['card']}")
        hand.append(data["card"])
        if should_stand():
            action = random.choice(["stand", "double"])
        else:
            action = "hit"
        perform_action(action)

@sio.on("player_busted")
def on_busted(data):
    print(f"[💥] {data['user']} ha sballato!")

@sio.on("user_stood")
def on_user_stood(data):
    print(f"[🧍] {data['user']} si è fermato.")

@sio.on("user_doubled")
def on_user_doubled(data):
    print(f"[✌️] {data['user']} ha raddoppiato e pescato {data['card']}")

@sio.on("player_action_done")
def on_action_done():
    print("[✔] Azione completata per tutti i giocatori")

@sio.on("results")
def on_results(data):
    print("[🏁] Risultati round ricevuti:")
    print(data)

@sio.on("error")
def on_error(data):
    print("[❌] Errore:", data.get("message"))

# === ACTIONS ===

def place_bet():
    amount = random.choice([10, 20, 50])
    print(f"[💸] Invio puntata: {amount}")
    sio.emit("bet", {"username": USERNAME, "amount": amount})

def perform_action(action):
    print(f"[➡️] Invio azione: {action.upper()}")
    sio.emit("player_action", {"username": USERNAME, "action": action})

def should_stand():
    # Simula se fermarsi in base al numero di carte (logica base)
    return len(hand) >= 3 or random.random() > 0.5

def main():
    for _ in range(5):
        try:
            sio.connect(SERVER_URL)
            break
        except Exception as e:
            print(f"[!] Connessione fallita: {e}")
            time.sleep(2)
    else:
        print("[✘] Impossibile connettersi al server.")
        return

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sio.disconnect()

if __name__ == "__main__":
    main()