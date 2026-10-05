import secrets

def main():
    admin_password = secrets.token_urlsafe(12)
    with open('.env', 'w') as f:
        f.write(f'SHARED_SECRET={secrets.token_urlsafe(32)}\n')

        f.write(f'GAME_SECRET_KEY={secrets.token_urlsafe(32)}\n')
        f.write(f'SECRET_KEY={secrets.token_urlsafe(32)}\n')

        f.write('ADMIN_USERNAME=admin\n')
        f.write(f'ADMIN_PASSWORD={admin_password}\n')
    #print(f'maintenance panel: log in as admin / {admin_password}')

if __name__ == "__main__":
    main()
