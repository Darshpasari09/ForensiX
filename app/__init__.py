
import os

from flask import Flask, render_template, session, redirect, url_for, request
from app.database import get_db_connection
from app.routes.new_case import case_entry_bp
from app.routes.investigation import investigation_bp
from app.routes.analytics import analytics_bp
from app.routes.auth import auth_bp
from flask_wtf.csrf import CSRFProtect


def create_app():
    app = Flask(__name__)

    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "FLASK_SECRET_KEY is not set. Set it in your terminal before starting ForensiX."
        )

    app.config["SECRET_KEY"] = secret_key
    app.config["WTF_CSRF_ENABLED"] = True 
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    
    CSRFProtect(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(case_entry_bp)
    app.register_blueprint(investigation_bp)
    app.register_blueprint(analytics_bp)

    @app.before_request
    def require_login():
        if request.endpoint in ("auth.login", "auth.logout", "static"):
            return None

        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))

    @app.route("/")
    def home():
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("SELECT DATABASE()")
            database_name = cursor.fetchone()[0]
        finally:
            cursor.close()
            connection.close()

        return render_template(
            "index.html",
            database_name=database_name
        )

    return app
