# init_db.py

from db import get_db_connection

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # users-Tabelle
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    """)

    # recurring_entries-Tabelle
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recurring_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        description TEXT,
        "usage" TEXT,
        amount REAL,
        duration INTEGER,
        start_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # transactions-Tabelle
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT,
        description TEXT,
        "usage" TEXT,
        amount REAL,
        paid INTEGER DEFAULT 0,
        recurring_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(recurring_id) REFERENCES recurring_entries(id)
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("SQLite-Datenbank initialisiert.")
