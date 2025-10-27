import os, sqlite3
from libsql_client import create_client_sync
try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env locally; harmless on Render
except Exception:
    pass

USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"
SQLITE_PATH = os.getenv("SQLITE_PATH", "database/medicalstore.db")

class SQLiteClient:
    """Minimal shim to mimic libsql_client's .execute(...).rows API."""
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys=ON;")

    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params or [])
        # Try to fetch rows (DDL/INSERT won't have any; that's fine)
        rows = []
        try:
            rows = cur.fetchall()
        except sqlite3.ProgrammingError:
            pass
        self.conn.commit()
        return type("ExecResult", (), {"rows": rows})

if USE_SQLITE:
    client = SQLiteClient(SQLITE_PATH)
else:
    db_url = os.getenv("TURSO_URL")
    auth_token = os.getenv("TURSO_AUTH_TOKEN")
    if not db_url or not auth_token:
        raise RuntimeError("Missing TURSO_URL or TURSO_TOKEN in .env")

    client = create_client_sync(url=db_url, auth_token=auth_token)