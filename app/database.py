import mysql.connector

from app.config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    MYSQL_SSL_CA,
)


def get_db_connection():
    connection_args = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DATABASE,
        "connection_timeout": 10,
    }

    # Verify the server certificate when a CA certificate is configured.
    if MYSQL_SSL_CA:
        connection_args["ssl_ca"] = MYSQL_SSL_CA
        connection_args["ssl_verify_cert"] = True
        connection_args["ssl_verify_identity"] = True

    return mysql.connector.connect(**connection_args)