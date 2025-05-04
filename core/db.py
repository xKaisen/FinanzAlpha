import os
import sys
import shutil
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# ─── 1. Basis-Pfad ermitteln ────────────────────────────────────────────────
APP_NAME = "FinanzApp"
if sys.platform == "win32":
    base_config = os.environ.get("APPDATA", os.path.expanduser("~"))
else:
    base_config = os.path.expanduser("~/.config")
USER_DIR = os.path.join(base_config, APP_NAME)
os.makedirs(USER_DIR, exist_ok=True)

# ─── 2. DB-Pfad festlegen ──────────────────────────────────────────────────
DB_FILENAME = os.environ.get("DATABASE_FILE", "finanz_app.db")
DB_PATH = (
    DB_FILENAME
    if os.path.isabs(DB_FILENAME)
    else os.path.join(USER_DIR, DB_FILENAME)
)
DB_PATH = os.path.abspath(DB_PATH)

# ─── 3. sqlite3-Verbindung ─────────────────────────────────────────────────
def get_db_connection() -> sqlite3.Connection:
    """
    Gibt eine sqlite3.Connection zurück, die dict-like rows liefert.
    Legt die DB bei Bedarf im USER_DIR an oder kopiert sie aus dem Bundle.
    Führt im Desktop-Modus Schema-Migration inklusive Cascade-Setup aus.
    """
    # Nur im Desktop-Modus (wenn keine DATABASE_FILE gesetzt)
    if "DATABASE_FILE" not in os.environ:
        BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        SOURCE_DB = os.path.join(BUNDLE_DIR, DB_FILENAME)
        if not os.path.isfile(DB_PATH):
            if os.path.isfile(SOURCE_DB):
                shutil.copy2(SOURCE_DB, DB_PATH)
            else:
                open(DB_PATH, "a").close()

    print(f"[DEBUG] Verwende Datenbank: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # SQLite: Foreign‑Keys aktivieren, damit ON DELETE CASCADE wirkt
    conn.execute("PRAGMA foreign_keys = ON;")

    # Schema‑Migration nur im Desktop‑Modus
    if "DATABASE_FILE" not in os.environ:
        _ensure_schema(conn)

    return conn

# ─── 4. SQLAlchemy Engine & Session ────────────────────────────────────────
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=False)
Session = scoped_session(sessionmaker(bind=engine))

def init_db():
    """
    Initialisiert alle Tabellen, wie sie in core/models.py definiert sind.
    """
    from core.models import Base
    Base.metadata.create_all(engine)

# ─── 5. Schema‑Migration für Desktop ────────────────────────────────────────
def _ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Stellt sicher, dass:
     - die User-Tabelle existiert und ggf. Spalte is_admin ergänzt wird
     - die Foreign-Key-Migration für ON DELETE CASCADE ausgeführt wird
    """
    cur = conn.cursor()

    # 5.1 Tabelle "users" anlegen, falls sie fehlt
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        # Danach Cascade-Migration prüfen (wird dann nichts tun, weil tables neu)
        _migrate_to_cascade(conn)
        return

    # 5.2 Spalte is_admin prüfen
    cur.execute("PRAGMA table_info(users)")
    cols = [row[1].lower() for row in cur.fetchall()]
    if "is_admin" not in cols:
        cur.execute(
            "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
        )

    # Index für genau einen Admin
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS one_admin_only
        ON users (is_admin) WHERE is_admin = 1
    """)
    conn.commit()

    # 5.3 Cascade-Migration für recurring_entries ↔ transactions
    _migrate_to_cascade(conn)


def _migrate_to_cascade(conn: sqlite3.Connection) -> None:
    """
    Prüft, ob transactions.recurring_id bereits ON DELETE CASCADE hat.
    Falls nicht, baut recurring_entries und transactions mit Cascade neu auf.
    """
    cur = conn.cursor()

    # Prüfen auf existierenden FK mit ON DELETE CASCADE
    cur.execute("PRAGMA foreign_key_list(transactions)")
    fks = cur.fetchall()
    for fk in fks:
        # Format: (id, seq, table, from, to, on_update, on_delete, match)
        if fk[2] == 'recurring_entries' and fk[6].upper() == 'CASCADE':
            return  # Schon migriert

    # Migration durchführen
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.executescript("""
    BEGIN TRANSACTION;
    -- Neue recurring_entries mit Cascade auf users
    CREATE TABLE recurring_entries_new (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      description TEXT,
      usage TEXT,
      amount REAL,
      duration INTEGER,
      start_date TEXT,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    -- Neue transactions mit Cascade auf recurring_entries und users
    CREATE TABLE transactions_new (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      date TEXT NOT NULL,
      description TEXT,
      "usage" TEXT,
      amount REAL,
      paid INTEGER,
      recurring_id INTEGER,
      FOREIGN KEY(user_id)    REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY(recurring_id) REFERENCES recurring_entries(id) ON DELETE CASCADE
    );
    -- Daten übernehmen
    INSERT INTO recurring_entries_new
      SELECT id, user_id, description, usage, amount, duration, start_date
      FROM recurring_entries;
    INSERT INTO transactions_new
      SELECT id, user_id, date, description, "usage", amount, paid, recurring_id
      FROM transactions;
    -- Alte Tabelllen ersetzen
    DROP TABLE transactions;
    DROP TABLE recurring_entries;
    ALTER TABLE recurring_entries_new RENAME TO recurring_entries;
    ALTER TABLE transactions_new      RENAME TO transactions;
    COMMIT;
    PRAGMA foreign_keys = ON;
    """)
    conn.commit()
