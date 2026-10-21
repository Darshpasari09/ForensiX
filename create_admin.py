
import getpass

from werkzeug.security import generate_password_hash
from app.database import get_db_connection


def main():
    username = input("New admin username: ").strip()
    full_name = input("Admin full name: ").strip()
    password = getpass.getpass("New admin password: ")
    confirm = getpass.getpass("Confirm password: ")

    if not username or not full_name or not password:
        print("All fields are required.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    if len(password) < 12:
        print("Use a password with at least 12 characters.")
        return

    connection = None
    cursor = None

    try:
        password_hash = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s)
            """,
            (username, password_hash, full_name, "ADMIN")
        )

        connection.commit()
        print("Administrator account created successfully.")

    except Exception as error:
        if connection is not None:
            connection.rollback()

        print("Could not create administrator account:", error)

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
