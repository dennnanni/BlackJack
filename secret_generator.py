from cryptography.fernet import Fernet
from pathlib import Path
import sys

def main():
    env_path = Path(".env")
    force = "-f" in sys.argv

    if env_path.exists() and not force:
        print(".env already exists. Use -f to overwrite.")
        return

    if force and env_path.exists():
        print("Overwriting existing .env file.")

    secret = Fernet.generate_key().decode()
    env_path.write_text(f"SHARED_SECRET={secret}\n")

if __name__ == "__main__":
    main()
