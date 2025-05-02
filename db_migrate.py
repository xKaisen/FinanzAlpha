# db_migrate.py  – einmal beim Start aufrufen
from db import get_db_connection

def ensure_admin_column():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = [row[1].lower() for row in cur.fetchall()]
        if "is_admin" not in cols:
            cur.execute(
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_admin_only "
                "ON users (is_admin) WHERE is_admin = 1"
            )
            conn.commit()
