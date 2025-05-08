# sync.py

import os
import time
import logging
import requests
import sqlite3
import json
from datetime import datetime
from core.db import Session           # Für Remote‑DB‑Session (SQLAlchemy)
from core.models import User, SomeModel, RecurringEntry, LocalChange  # Passe ggf. an

# ─── Konfiguration ─────────────────────────────────────────────
API_PUSH    = os.getenv("SYNC_PUSH_URL", "http://127.0.0.1:5000/api/sync/push")
API_PULL    = os.getenv("SYNC_PULL_URL", "http://127.0.0.1:5000/api/sync/pull")
STATE_FILE  = os.getenv("SYNC_STATE_FILE", "last_pull_ts.txt")
LOCAL_DB    = os.getenv("SQLITE_PATH", "local.db")
LOG_LEVEL   = os.getenv("SYNC_LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=LOG_LEVEL,
                    format="%(asctime)s [sync] %(levelname)s: %(message)s")


def get_local_conn():
    """Öffnet (oder legt an) die lokale SQLite‑DB."""
    return sqlite3.connect(LOCAL_DB)


def ensure_local_schema():
    """Legt die lokalen Tabellen in local.db an, falls sie nicht existieren."""
    conn = get_local_conn()
    cur  = conn.cursor()

    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id            INTEGER PRIMARY KEY,
      username      TEXT    UNIQUE NOT NULL,
      password_hash TEXT    NOT NULL,
      is_admin      INTEGER NOT NULL DEFAULT 0,
      created_at    TEXT    NOT NULL,
      updated_at    TEXT    NOT NULL
    );
    """)

    # some_model
    cur.execute("""
    CREATE TABLE IF NOT EXISTS some_model (
      id            INTEGER PRIMARY KEY,
      name          TEXT    NOT NULL,
      last_modified TEXT    NOT NULL
    );
    """)

    # recurring_entries
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recurring_entries (
      id          INTEGER PRIMARY KEY,
      user_id     INTEGER NOT NULL,
      description TEXT    NOT NULL,
      usage       TEXT    NOT NULL,
      amount      REAL    NOT NULL,
      duration    INTEGER NOT NULL,
      start_date  TEXT    NOT NULL,
      created_at  TEXT    NOT NULL,
      updated_at  TEXT    NOT NULL
    );
    """)

    # changelog_local
    cur.execute("""
    CREATE TABLE IF NOT EXISTS changelog_local (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      table_name  TEXT    NOT NULL,
      operation   TEXT    NOT NULL,
      row_id      INTEGER NOT NULL,
      data        TEXT,
      timestamp   TEXT    NOT NULL
    );
    """)

    # transactions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
      id             INTEGER PRIMARY KEY,
      user_id        INTEGER NOT NULL,
      date           TEXT    NOT NULL,
      description    TEXT    NOT NULL,
      "usage"        TEXT    NOT NULL,
      amount         REAL    NOT NULL,
      paid           INTEGER NOT NULL,
      recurring_id   INTEGER,
      FOREIGN KEY(user_id) REFERENCES users(id),
      FOREIGN KEY(recurring_id) REFERENCES recurring_entries(id)
    );
    """)

    conn.commit()
    conn.close()
    logging.info("✅ Lokales SQLite‑Schema initialisiert.")


def load_last_pull_ts() -> str | None:
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_last_pull_ts(ts: str) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(ts)


def get_model_for_table(table: str):
    """Mappt Tabellenname auf SQLAlchemy‑Model."""
    if table == "users":
        return User
    if table == "some_model":
        return SomeModel
    if table == "recurring_entries":
        return RecurringEntry
    # … weitere Models …
    return None


def push_changes(user_id: int | None = None) -> None:
    """Liest changelog_local in SQLite und pusht alle Einträge ans API_PUSH."""
    conn = get_local_conn()
    cur  = conn.cursor()

    if user_id is not None:
        cur.execute(
            "SELECT id, table_name, operation, row_id, data, timestamp "
            "FROM changelog_local WHERE row_id = ? ORDER BY timestamp",
            (user_id,)
        )
    else:
        cur.execute(
            "SELECT id, table_name, operation, row_id, data, timestamp "
            "FROM changelog_local ORDER BY timestamp"
        )

    rows = cur.fetchall()
    if not rows:
        logging.debug("Keine lokalen Änderungen zum Push gefunden.")
        conn.close()
        return

    payload = []
    for _id, table, op, row_id, data_json, ts in rows:
        payload.append({
            "table": table,
            "op":    op,
            "id":    row_id,
            "data":  json.loads(data_json) if data_json else {},
            "ts":    ts,
        })

    try:
        resp = requests.post(API_PUSH, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info(f"{len(rows)} Änderung(en) erfolgreich gepusht.")
    except requests.RequestException as e:
        logging.warning(f"Push fehlgeschlagen: {e}")
        conn.close()
        return

    # Lösche alle Einträge im lokalen Changelog
    cur.execute("DELETE FROM changelog_local")
    conn.commit()
    conn.close()


def apply_remote_change(change: dict, session) -> None:
    """Wendet eine Remote-Änderung auf die Remote‑DB (SQLAlchemy) an."""
    table = change["table"]
    op    = change["op"]
    row_id= change["id"]
    data  = change.get("data", {})

    Model = get_model_for_table(table)
    if not Model:
        logging.debug(f"Unbekannte Tabelle beim Pull: {table}")
        return

    if op == "insert":
        session.merge(Model(**data))
    elif op == "update":
        obj = session.get(Model, row_id)
        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
    elif op == "delete":
        obj = session.get(Model, row_id)
        if obj:
            session.delete(obj)


def pull_changes() -> None:
    """Fragt API_PULL nach Änderungen seit letztem Timestamp und wendet sie an."""
    since = load_last_pull_ts()
    params = {"since": since} if since else {}

    try:
        resp = requests.get(API_PULL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.warning(f"Pull fehlgeschlagen: {e}")
        return

    remote_changes = resp.json()
    if not remote_changes:
        logging.debug("Keine Remote-Änderungen zum Pull gefunden.")
        return

    session = Session()
    for c in remote_changes:
        apply_remote_change(c, session)

    last_ts = remote_changes[-1]["ts"]
    save_last_pull_ts(last_ts)
    session.commit()
    logging.info(f"Pull erfolgreich, letzter Timestamp: {last_ts}")


def sync(user_id: int | None = None) -> None:
    """Komplette Synchronisation: Push + Pull."""
    logging.info("🔄 Starte Synchronisation …")
    ensure_local_schema()
    push_changes(user_id)
    pull_changes()
    logging.info("✅ Synchronisation abgeschlossen.")


def main_loop(interval: int = 60) -> None:
    ensure_local_schema()
    while True:
        sync()
        time.sleep(interval)


if __name__ == "__main__":
    main_loop()
