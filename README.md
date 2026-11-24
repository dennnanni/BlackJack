# BlackJack

A distributed multiplayer blackjack game.

## Installation

### Requirements

- Docker with Docker Compose
- Python 3.12+ (to generate the secrets file)
- Poetry (only to run the tests locally)

### Setup

1. Clone the repository and move into it:

   ```bash
   git clone <repo-url>
   cd BlackJack
   ```

2. Generate the `.env` file with random secrets and the admin credentials:

   ```bash
   python secret_generator.py
   ```

   Alternatively, copy `.env-template` to `.env` and fill in the values by hand.

3. Build and start all the services:

   ```bash
   ./startup.sh
   ```

   This builds the base `ppython` image (Python + Poetry) if it is missing, then runs `docker compose up --build`.

### Usage

- Player site: http://localhost:5002
- Admin panel: http://localhost:5002/admin (username and password are in `.env`)
- Game servers: ports `8000` and `8001`. Players are redirected there automatically after choosing to play.

### Running the tests

```bash
poetry install
poetry run pytest
```
