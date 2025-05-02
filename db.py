import os
import sys
import shutil
import sqlite3

# ---------------------------------------------------------------------------
# Wo die DB wirklich liegen soll: im AppData-Ordner des aktuellen Users
# ---------------------------------------------------------------------------
APP_NAME = "FinanzApp"
if sys.platform == "win32":
    base_config = os.environ.get("APPDATA", os.path.expanduser("~"))
else:
    base_config = os.path.expanduser("~/.config")
USER_DIR = os.path.join(base_config, APP_NAME)
os.makedirs(USER_DIR, exist_ok=True)

DB_FILENAME = "finanz_app.db"
TARGET_DB = os.path.join(USER_DIR, DB_FILENAME)

# ---------------------------------------------------------------------------
# Pfad zur gebündelten DB (nur, falls du eine initiale Vorlage mitliefern willst)
# ---------------------------------------------------------------------------
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
SOURCE_DB = os.path.join(BUNDLE_DIR, DB_FILENAME)

def get_db_connection() -> sqlite3.Connection:
    """
    Stellt eine Verbindung zur SQLite-DB im Benutzer-Ordner her.
    Wenn dort noch keine DB liegt, wird sie aus dem Bundle kopiert oder
    neu angelegt.
    """
    # Erstmal sicherstellen, dass TARGET_DB existiert
    if not os.path.isfile(TARGET_DB):
        if os.path.isfile(SOURCE_DB):
            # Liefer-DB kopieren
            shutil.copy2(SOURCE_DB, TARGET_DB)
        else:
            # leere DB wird beim ersten connect automatisch angelegt
            open(TARGET_DB, "a").close()

    conn = sqlite3.connect(TARGET_DB)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn

# ---------------------------------------------------------------------------
# Private Helfer: Schema-Migration
# ---------------------------------------------------------------------------
def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # Tabelle "users" anlegen, falls sie fehlt
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    if not cur.fetchone():
        cur.execute(
            """CREATE TABLE users (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   username      TEXT UNIQUE NOT NULL,
                   password_hash TEXT NOT NULL,
                   is_admin      BOOLEAN NOT NULL DEFAULT 0
               )"""
        )
        conn.commit()
        return

    # Spalte is_admin prüfen
    cur.execute("PRAGMA table_info(users)")
    cols = [row[1].lower() for row in cur.fetchall()]
    if "is_admin" not in cols:
        cur.execute(
            "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
        )

    # Index für genau einen Admin
    cur.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS one_admin_only
           ON users (is_admin) WHERE is_admin = 1"""
    )

    conn.commit()
