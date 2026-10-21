
import getpass

from werkzeug.security import generate_password_hash
from app.database import get_db_connection


VALID_ROLES = ("ADMIN", "INVESTIGATOR", "FORENSIC_ANALYST", "VIEWER")


def main():
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip()
    badge_id = input("Badge ID (leave blank if not applicable): ").strip() or None
    role = input("Role (ADMIN/INVESTIGATOR/FORENSIC_ANALYST/VIEWER): ").strip().upper()

    if not username or not full_name:
        print("Username and full name are required.")
        return

    if role not in VALID_ROLES:
        print("Invalid role.")
        return

    password = getpass.getpass("Password (minimum 12 characters): ")
    confirm = getpass.getpass("Confirm password: ")

    if len(password) < 12:
        print("Password must be at least 12 characters.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, full_name, badge_id, role)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                username,
                generate_password_hash(password),
                full_name,
                badge_id,
                role
            )
        )

        connection.commit()
        print(f"Account '{username}' created with role {role}.")

    except Exception as error:
        if connection is not None:
            connection.rollback()
        print("Could not create account:", error)

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
