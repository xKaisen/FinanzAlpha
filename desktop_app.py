# desktop_app.py

import os
import sys
import threading
import time
import socket
import webview
import logging
from dotenv import load_dotenv

# ─── 1) Erzwinge den Offline‑Modus und SQLite‑Pfad ───────────
os.environ["APP_MODE"]    = "offline"
os.environ["SQLITE_PATH"] = "local.db"

# ─── 2) Projekt‑Root ganz vorne ins PYTHONPATH ────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ─── 3) .env laden (überschreibt APP_MODE nicht) ─────────────
load_dotenv()

# ─── 4) Module importieren (DB zuerst, damit init_db verfügbar ist) ───
from core.db import init_db
from sync import sync
from core.auth import login_user
from app import create_app

# ─── 5) Logging konfigurieren ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ─── 6) Lokales Schema initialisieren ──────────────────────────
logger.info("🔧 Lege lokale SQLite‑Tabellen an…")
init_db()
logger.info("✅ Lokale Tabellen bereit.")


def start_periodic_sync(user_id: int, interval: int = 60) -> None:
    """Hintergrund-Thread: Push/Pull im Sekundentakt."""
    def loop():
        while True:
            try:
                logger.info("🔄 Starte periodische Synchronisation...")
                sync(user_id)
                logger.info("✅ Periodische Synchronisation erfolgreich.")
            except Exception as e:
                logger.warning(f"Periodische Synchronisation fehlgeschlagen: {e}", exc_info=True)
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def run_flask():
    """Flask-Server im Hintergrund starten."""
    try:
        logger.info("⚙️  Starte Flask‑App…")
        app = create_app()
        logger.info("✅ Flask‑App erstellt.")
        app.run(port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Fehler beim Starten der Flask‑App: {e}", exc_info=True)


def wait_for_flask_ready(port: int = 5000, timeout: int = 15) -> bool:
    """Wartet, bis der Flask‑Server erreichbar ist."""
    logger.info(f"⏳ Warte auf Flask‑Server auf Port {port}…")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                logger.info("✅ Flask‑Server erreichbar.")
                return True
        except Exception:
            time.sleep(0.5)
    logger.error(f"❌ Timeout ({timeout}s): Flask‑Server nicht erreichbar.")
    return False


if __name__ == '__main__':
    logger.info("🚀 Starte FinanzAlpha Desktop‑Modus…")

    # 1) Flask im Hintergrund booten
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    if not wait_for_flask_ready():
        logger.critical("🛑 Abbruch: Flask‑Server konnte nicht gestartet werden.")
        exit(1)

    # 2) Auto‑Login & erste Synchronisation
    username = os.getenv('DESKTOP_USERNAME')
    password = os.getenv('DESKTOP_PASSWORD')
    if username and password:
        ok, info = login_user(username, password)
        if ok:
            user_id, _ = info
            logger.info(f"🔄 Führe erste Synchronisation für User {user_id} durch…")
            try:
                sync(user_id)
                logger.info("✅ Erste Synchronisation erfolgreich.")
            except Exception as e:
                logger.warning(f"Erste Synchronisation fehlgeschlagen: {e}", exc_info=True)
            start_periodic_sync(user_id)
        else:
            logger.warning(f"⚠️  Auto‑Login fehlgeschlagen: {info}")
    else:
        logger.info("⚙️  Kein Auto‑Login konfiguriert, bitte manuell anmelden.")

    # 3) Desktop‑Fenster öffnen
    try:
        logger.info("🌐 Öffne Webview‑Fenster…")
        webview.create_window(
            title="FinanzAlpha Desktop",
            url="http://127.0.0.1:5000?desktop=1",
            width=1024,
            height=768,
        )
        webview.start()
        logger.info("✅ Webview geschlossen.")
    except Exception as e:
        logger.error(f"❌ Fehler beim Webview‑Start: {e}", exc_info=True)

    logger.info("🔚 FinanzAlpha Desktop‑Modus beendet.")
