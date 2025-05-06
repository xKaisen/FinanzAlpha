# desktop_app.py
import threading
import time
import socket
import webview
import logging # Importiere Logging
from app import create_app
# check_for_update_result wird nicht mehr direkt hier aufgerufen, daher nicht importiert
# from updater import check_for_update_result

# Konfiguriere Logging für desktop_app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_flask():
    """Startet die Flask-App in diesem Thread."""
    try:
        logger.info("⚙️  Starte Flask-App...")
        # Erstelle die Flask-App Instanz
        app = create_app()
        logger.info("✅ Flask-App erstellt.")
        # Starte den Flask-Server. use_reloader=False ist wichtig im Multithreading/Desktop-Kontext.
        # debug=False ist wichtig für die Produktivumgebung.
        app.run(port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Fehler beim Starten der Flask-App: {e}", exc_info=True) # exc_info=True loggt den Traceback


def wait_for_flask_ready(port=5000, timeout=15):
    """
    Wartet, bis der Flask-Server auf dem angegebenen Port erreichbar ist.
    """
    logger.info(f"⏳ Warte auf Flask-Server auf Port {port}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Versuche, eine Socket-Verbindung aufzubauen
            with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
                # Wenn die Verbindung erfolgreich ist, ist der Server bereit
                logger.info("✅ Flask-Server erreichbar.")
                return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            # Server noch nicht bereit, oder temporärer Fehler
            # logger.debug("Verbindung fehlgeschlagen, versuche es erneut...")
            pass # Versuche es im nächsten Schleifendurchlauf erneut
        except Exception as e:
            # logger.warning(f"⚠️  Unerwarteter Fehler beim Verbindungscheck: {e}")
            pass # Bei anderen Fehlern auch einfach warten und erneut versuchen

        time.sleep(0.5) # Kurze Pause vor dem nächsten Versuch

    # Timeout erreicht, Server nicht erreichbar
    logger.error(f"❌ Timeout ({timeout}s): Flask-Server auf Port {port} nicht erreichbar.")
    return False

if __name__ == '__main__':
    logger.info("🚀 Starte FinanzAlpha Desktop-Modus...")

    # --- Update-Prüfung beim Start ---
    # Die initiale Update-Prüfung wird jetzt hauptsächlich über den Context Processor
    # in app.py getriggert, wenn die Webview die erste Seite lädt.
    # Eine separate, blockierende Prüfung hier wäre nur nötig, wenn du z.B.
    # VOR dem Öffnen des Fensters ein Update erzwingen oder melden möchtest.
    # Wenn check_for_update() in updater.py Caching hat, ist ein wiederholter Aufruf
    # vom Context Processor beim Navigieren unproblematisch.
    # check_for_update_result() wurde hier entfernt, da es unklar war, was genau es tut
    # und wie es mit check_for_update() in app.py zusammenhängt.

    # Starte Flask-Server im Hintergrund-Thread (Daemon-Thread beendet sich, wenn Hauptthread endet)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Warte, bis der Flask-Server gestartet ist
    if wait_for_flask_ready():
        try:
            logger.info("🌐 Öffne Webview-Fenster...")
            # Erstelle das pywebview-Fenster
            webview.create_window(
                title="FinanzAlpha Desktop", # Fenstertitel
                # Lade die Flask-App über localhost. Füge ?desktop=1 hinzu,
                # um die Desktop-spezifischen Features (wie Update-Check-UI) zu aktivieren.
                url="http://127.0.0.1:5000?desktop=1",
                width=1024, # Standardbreite
                height=768, # Standardhöhe
                # Optional: resizable=True, fullscreen=False etc.
            )
            # Starte den pywebview Event Loop (blockiert, bis das Fenster geschlossen wird)
            webview.start()
            logger.info("✅ Webview-Fenster geschlossen.")

        except Exception as e:
            logger.error(f"❌ Fehler beim Öffnen oder Ausführen des Webview-Fensters: {e}", exc_info=True)
    else:
        logger.critical("🛑 Abbruch: Flask-Server konnte nicht gestartet oder erreicht werden. Bitte prüfe Fehler in der Konsole.")

    logger.info("FinanzAlpha Desktop-Modus beendet.")