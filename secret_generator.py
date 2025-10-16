from cryptography.fernet import Fernet

def main():
    secret = Fernet.generate_key()
    with open('.env', 'w') as f:
        f.write(f'SHARED_SECRET={secret.decode()}')

if __name__ == "__main__":
    main()