
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from urllib.parse import urlparse
from app.database import get_db_connection

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter both username and password.", "error")
            return render_template("login.html")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT user_id, username, password_hash, full_name, role
                FROM users
                WHERE username = %s
                """,
                (username,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                session["full_name"] = user["full_name"]
                session["role"] = user["role"]

                destination = request.args.get("next", "")
                parsed = urlparse(destination)

                if destination and not parsed.scheme and not parsed.netloc and destination.startswith("/") and not destination.startswith("//"):
                    return redirect(destination)

                return redirect(url_for("home"))

            flash("Invalid username or password.", "error")

        except Exception:
            app_logger = __name__
            import logging
            logging.getLogger(app_logger).exception("Login database error")
            flash("Unable to process login right now. Please try again.", "error")

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None and connection.is_connected():
                connection.close()

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
