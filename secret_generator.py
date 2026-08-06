import secrets


def main():
    with open('.env', 'w') as f:
        f.write(f'SHARED_SECRET={secrets.token_urlsafe(32)}\n')


if __name__ == "__main__":
    main()
