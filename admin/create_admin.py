"""
One-time CLI to create an admin account.

Usage:
    python -m admin.create_admin <username> <password>
"""
import sys

from admin.auth import hash_password
from storage import store


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m admin.create_admin <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    if store.get_admin_by_username(username):
        print(f"Admin '{username}' already exists. Use the Settings page to change their password instead.")
        sys.exit(1)

    store.create_admin(username, hash_password(password))
    print(f"Admin '{username}' created.")


if __name__ == "__main__":
    main()
