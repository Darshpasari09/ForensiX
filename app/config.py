import os

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "forensix")

# Optional CA certificate path for secure hosted MySQL connections.
MYSQL_SSL_CA = os.getenv("MYSQL_SSL_CA") or None

if not MYSQL_PASSWORD:
    raise RuntimeError("MYSQL_PASSWORD environment variable is not set.")