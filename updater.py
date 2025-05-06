# updater.py (Vollständig & Angepasst - MUSS vervollständigt werden!)
# Speichere diese Datei im SELBEN VERZEICHNIS wie deine app.py

import requests # Benötigt 'pip install requests'
import logging # Importiere Logging
import time
import os # Benötigt für Pfade, Umgebungsvariablen
import sys # Benötigt für Prozess-Management (sys.exit, sys.executable)
import subprocess # Benötigt für das Starten des neuen Prozesses (subprocess.Popen)
import shutil # Benötigt für das Kopieren/Verschieben von Dateien (shutil.copyfileobj, os.replace, shutil.rmtree)
import tempfile # Benötigt für temporäre Verzeichnisse/Dateien
import re # Benötigt für Versionsprüfung (aus PySide6 Version übernommen)
from pathlib import Path # Benötigt für Pfad-Objekte
import datetime # Benötigt für Zeitstempel (z.B. für Logs, tempfiles)
# from packaging.version import Version # Optional: Alternative zu version_tuple/is_newer_version (benötigt 'pip install packaging')

# --- Konfiguriere Logging für updater.py ---
# Dies stellt sicher, dass Log-Meldungen aus updater.py sichtbar sind.
# Wenn der root logger in app.py bereits konfiguriert ist, kann das hier redundant sein, schadet aber nicht.
# Füge dies am Anfang deiner updater.py ein
# updater.py
# ... imports ...

# --- Konfiguriere Logging für updater.py ---
# Dies stellt sicher, dass Log-Meldungen aus updater.py sichtbar sind.
# Wenn der root logger in app.py bereits konfiguriert ist, kann das hier redundant sein, schadet aber nicht.
# Füge dies am Anfang deiner updater.py ein
if not logging.root.handlers: # Prüfe, ob der Root-Logger bereits Handler hat
    try:
        # Annahme: _get_app_data_base_dir ist aus core/version.py verfügbar oder hier definiert
        # Annahme: _get_log_file_path ist hier definiert oder importiert
        # Wenn du Datei-Logging für den Updater willst, uncommentiere und implementiere den Code hier.
        # Solange der try Block leer ist (nur Kommentare), MUSST du 'pass' einfügen.
        pass # <-- Füge diese eingerückte Zeile hier ein, um den IndentationError zu beheben!

        # Beispiel (Funktionen müssen definiert oder importiert sein, und Zeilen einkommentiert):
        # FIRMENNAME = "DeineFirma" # <-- Muss gesetzt sein
        # ANWENDUNGSNAME = "FinanzAlpha" # <-- Muss gesetzt sein
        # LOG_DATEINAME = "update.log" # <-- Kann angepasst werden
        # log_file_full_path = _get_log_file_path(LOG_DATEINAME) # Diese Funktion muss existieren
        # logging.basicConfig(filename=log_file_full_path, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', encoding='utf-8')
        # logging.info("-" * 60)
        # logging.info("Datei-Logging für Updater konfiguriert.")


    except Exception as e:
        # Fallback auf Konsolen-Logging, wenn der try Block fehlschlägt (z.B. Path-Fehler)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.error(f"FEHLER: Konfiguration des Datei-Loggings für Updater fehlgeschlagen: {e}. Logge zur Konsole.")

# Das ist der korrekte Platz für den Logger nach dem if/try/except Block
logger = logging.getLogger(__name__) # Empfohlen: Eigener Logger für das Modul
# logger.setLevel(logging.DEBUG) # Optional: Setze das Level für diesen Logger feiner


# Import der Anwendungsversion ... (der Rest des Codes folgt hier)
# ... GITHUB_ASSET_NAME = "FinanzAlpha.exe" ...
# ... fetch_latest_release_data ...
# ... version_tuple ...
# ... is_newer_version ...
# ... find_asset_url ...
# ... check_for_update ...
# ... download_file ...
# ... install_update ...
# ... cleanup_path ...

logger = logging.getLogger(__name__) # Empfohlen: Eigener Logger für das Modul
# logger.setLevel(logging.DEBUG) # Optional: Setze das Level für diesen Logger feiner


# Import der Anwendungsversion (immer noch benötigt, um die aktuelle Version zu kennen)
# Dies funktioniert nur, wenn core/version.py korrekt importiert werden kann.
try:
    from core.version import __version__ # __version__ kommt weiterhin von core/version.py
    logger.info(f"Importierte aktuelle App-Version: {__version__}")
except ImportError:
    logger.error("Konnte core.version nicht importieren. __version__ ist nicht verfügbar.")
    __version__ = "0.0.0" # Fallback Version, wichtig für is_newer_version, um Absturz zu vermeiden

# --- Konfiguration für dein GitHub Repository ---
# >>>>> PASSE DIESE KONSTANTEN AN <<<<<
GITHUB_OWNER = "xKaisen" # Dein GitHub Username oder deine Organisation
GITHUB_REPO = "FinanzAlpha"    # Der Name deines GitHub Repositorys
# HIER MUSST DU DEN EXAKTEN NAMEN DEINES ASSETS IM GITHUB RELEASE EINFÜGEN!
# Dieser Name MUSS EXAKT mit dem Namen der Datei in deinem Release übereinstimmen!
# Du hast mir den Namen gegeben: "FinanzAlpha.exe"
GITHUB_ASSET_NAME = "FinanzAlpha.exe" # <--- STELL SICHER, DASS DAS EXAKT DEIN ASSET-NAME IST!
# >>>>> ENDE ANPASSUNG <<<<<
# -----------------------------------------------


# --- Caching für Update-Status ---
# Speichert das Ergebnis des letzten Checks, um GitHub nicht bei jeder Anfrage zu spammen.
_cached_update_status: tuple[str | None, dict | None] | None = None
_cache_time: float = 0
_cache_duration: int = 3600 # Cache-Dauer in Sekunden (z.B. 1 Stunde)


# --- Übernommene Logik für Versionsvergleich (aus PySide6 Version) ---
# Passt für X.Y.Z, packaging.Version ist robuster für komplexere Schemas
def version_tuple(v: str):
    """Konvertiert eine Versionszeichenkette (z.B. '1.2.3') in ein Tupel von Integern."""
    # Stellt sicher, dass die Version das Format major.minor.patch hat
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if not match:
        logger.warning(f"Ungültiges Versionsformat für Tupelkonvertierung: '{v}'.")
        # Wirf hier einen Fehler, der oben abgefangen wird
        raise ValueError(f"Ungültiges Versionsformat: '{v}'")
    # Sicherstellen, dass alle Gruppen gefunden wurden
    if len(match.groups()) != 3:
         logger.warning(f"Versionsformat '{v}' hat nicht genau 3 Teile.")
         raise ValueError(f"Ungültiges Versionsformat: '{v}'")
    # map(int, ...) kann einen ValueError werfen, wenn Teile keine Zahlen sind
    try:
        return tuple(map(int, match.groups()))
    except ValueError:
         logger.warning(f"Versionsformat '{v}' enthält Nicht-Zahlen.")
         raise ValueError(f"Ungültiges Versionsformat: '{v}'")


def is_newer_version(latest: str, current: str) -> bool:
    """Vergleicht zwei Versionszeichenketten (angenommen X.Y.Z Format)."""
    if not latest or not current:
        logger.warning(f"Ungültige Versions-Strings für Vergleich: Remote='{latest}', Current='{current}'.") # <-- Nutze Logging
        return False # Kann nicht vergleichen

    try:
        # Entferne optional 'v' oder 'V' am Anfang des Remote-Versions-Strings für Konsistenz
        cleaned_latest_version_str = latest.lstrip('vV')

        # Verwende packaging.Version für robusten Vergleich (empfohlen!)
        # Wenn 'packaging' installiert ist, kannst du diesen Block nutzen:
        # from packaging.version import Version # Importieren, falls packaging verwendet wird
        # current_v = Version(current)
        # remote_v = Version(cleaned_latest_version_str)
        # is_newer = remote_v > current_v
        # logger.debug(f"Vergleich mit packaging: Aktuell={current_v}, Remote={remote_v}. Neuere verfügbar: {is_newer}")
        # return is_newer

        # Alternative: Nutze die übernommene tuple-basierte Logik (weniger robust, nur X.Y.Z)
        latest_t = version_tuple(cleaned_latest_version_str) # Konvertiere remote nach Tupel
        current_t = version_tuple(current) # Konvertiere current nach Tupel
        is_newer = latest_t > current_t
        logger.debug(f"Vergleich mit Tupel: Aktuell='{current}' ({current_t}), Neueste='{latest}' ({latest_t}). Neuere verfügbar: {is_newer}") # <-- Nutze Logging (debug level)
        return is_newer

    except ValueError as ve:
        # Fehler von version_tuple wird hier abgefangen
        logger.error(f"Fehler beim Vergleichen der Versionen '{latest}' und '{current}' aufgrund ungültigen Formats: {ve}") # <-- Nutze Logging
        return False
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Vergleichen der Versionen '{latest}' und '{current}': {e}", exc_info=True) # <-- Nutze Logging
        return False
# --- Ende Übernommene Versionslogik ---


def fetch_latest_release_data() -> dict | None:
    """Holt die neuesten Release-Daten von der GitHub API."""
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    headers = {"User-Agent": f"{GITHUB_REPO}Updater/1.0 (Kontakt: deine@email.adresse)"} # Guter User-Agent ist wichtig!

    # Optional: Füge einen GitHub Personal Access Token als Umgebungsvariable hinzu
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        logger.debug("Verwende GitHub Token für API-Anfrage.")

    try:
        logger.info(f"Sende Anfrage an GitHub API: {api_url}") # <-- Nutze Logging
        response = requests.get(api_url, headers=headers, timeout=15) # Erhöhe Timeout etwas
        response.raise_for_status() # Wirft eine Exception für schlechte Status-Codes (4xx, 5xx)

        remaining_calls = response.headers.get('X-RateLimit-Remaining')
        # reset_time = response.headers.get('X-RateLimit-Reset')
        logger.info(f"GitHub API Rate Limit: {remaining_calls} verbleibende Anfragen.")
        if remaining_calls is not None and int(remaining_calls) < 10:
             logger.warning("GitHub API Rate Limit fast erreicht.")
        # reset_time kann nützlich sein

        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Netzwerk- oder HTTP-Fehler beim Abrufen der Release-Daten von {api_url}: {e}") # <-- Nutze Logging
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"HTTP Status Code: {e.response.status_code}")
            # logger.error(f"Response Body: {e.response.text[:200]}...") # Logge Teil des Response Bodys bei Fehler (Vorsicht!)
        return None # Gib None zurück im Fehlerfall
    except Exception as e:
        logger.exception(f"Unerwarteter Fehler in fetch_latest_release_data:") # <-- Nutze Logging
        return None


# Funktion zum Finden der Asset-URL basierend auf dem exakten Namen (Korrigierte Logik!)
def find_asset_url(release_data: dict, asset_name: str) -> str | None:
    """
    Findet die Browser-Download-URL für ein Asset mit einem spezifischen Namen
    in den Release-Daten. Nutzt den konfigurierten GITHUB_ASSET_NAME.
    """
    if not release_data:
        logger.warning("Kann Asset nicht finden: Keine Release-Daten vorhanden.") # <-- Nutze Logging
        return None
    if not asset_name:
        logger.error("GITHUB_ASSET_NAME ist in updater.py nicht konfiguriert.") # <-- Nutze Logging
        return None # Konfiguration fehlt

    assets = release_data.get("assets", [])
    logger.debug(f"Suche Asset '{asset_name}'. Verfügbare Assets im Release: {[a.get('name', 'Unbekannt') for a in assets]}")

    for asset in assets:
        # Finde das Asset, dessen Name EXAKT mit dem konfigurierten Namen übereinstimmt
        if asset.get("name") == asset_name:
            download_url = asset.get("browser_download_url")
            if download_url:
                 logger.info(f"Asset '{asset_name}' gefunden. Download-URL: {download_url}") # <-- Nutze Logging
                 return download_url
            else:
                 logger.warning(f"Asset '{asset_name}' gefunden, hat aber keine browser_download_url.") # <-- Nutze Logging
                 return None # Asset gefunden, aber kein Download-Link

    logger.warning(f"Kein Asset namens '{asset_name}' im Release gefunden.") # <-- Nutze Logging
    return None # Asset nicht gefunden


# check_for_update Funktion (Angepasste Signatur & Logik)
def check_for_update(current_version: str) -> tuple[str | None, dict | None]:
    """
    Prüft auf GitHub, ob eine neuere Version der Desktop-App verfügbar ist
    als die aktuelle Version (übergeben als current_version). Verwendet Caching.
    Gibt (neueste_version_string, daten_fuer_download) oder (None, None) zurück.
    daten_fuer_download ist ein dict, das 'download_url', 'version' und 'asset_name' enthält.
    """
    global _cached_update_status, _cache_time # Zugriff auf globale Cache-Variablen

    # Cache prüfen
    # Stelle sicher, dass der Cache älter als die Cache-Dauer ist
    if time.time() - _cache_time < _cache_duration and _cached_update_status is not None:
        logger.info(f"Update-Status aus Cache geladen (gültig für {_cache_duration - (time.time() - _cache_time):.1f} weitere Sekunden).") # <-- Nutze Logging
        return _cached_update_status # Cache-Ergebnis zurückgeben

    # Cache ist alt oder nicht vorhanden, führe neuen Check durch
    logger.info(f"Cache abgelaufen oder leer. Führe neuen GitHub Update-Check durch. Aktuelle Version: {current_version}") # <-- Nutze Logging
    latest_version_string = None
    download_url = None
    release_data = None # Initialisieren
    update_data = None

    try:
        release_data = fetch_latest_release_data() # Hol die Daten vom API
        if release_data:
            # Extrahiere Versions-String (tag_name oder name)
            potential_latest_version_string = release_data.get("tag_name", "").lstrip("v")
            if not potential_latest_version_string:
                 potential_latest_version_string = release_data.get("name", "").lstrip("v") # Fallback

            # Wenn ein potenzieller Remote-Versions-String gefunden wurde UND dieser neuer ist als die aktuelle Version
            if potential_latest_version_string and is_newer_version(potential_latest_version_string, current_version): # <-- Nutzt current_version Argument & übernommene is_newer_version!
                latest_version_string = potential_latest_version_string # Eine neuere Version wurde gefunden

                # Finde den passenden Asset-Download-Link für die neueste Version, mit korrektem Namen
                download_url = find_asset_url(release_data, GITHUB_ASSET_NAME) # <-- Ruft die korrigierte find_asset_url auf!

                if not download_url:
                     # find_asset_url loggt bereits eine Warnung/Fehler
                     latest_version_string = None # Wenn Asset nicht gefunden, kein nutzbares Update

                else:
                     # Wenn Version neuer UND Asset gefunden, bereite Daten für den Download vor
                     update_data = {
                         "download_url": download_url,
                         "version": latest_version_string,
                         "asset_name": GITHUB_ASSET_NAME # Füge den Asset-Namen hinzu, nützlich für install_update
                     }

            else:
                # Keine neuere Version oder Versions-String ungültig
                if potential_latest_version_string:
                    logger.info(f"Aktuelle Version {current_version} ist aktuell oder neuer als {potential_latest_version_string}.") # <-- Nutze Logging
                # else: fetch_latest_release_data hat bereits geloggt, wenn kein Versions-String gefunden wurde
                # latest_version_string bleibt None
                # download_url bleibt None
                # update_data bleibt None

        # else: fetch_latest_release_data hat bereits einen Fehler geloggt und None zurückgegeben


    except Exception as e:
        # Fange alle anderen unerwarteten Fehler im check_for_update Prozess ab
        logger.exception("Unerwarteter Fehler im check_for_update Prozess:") # <-- Nutze Logging für Exception
        latest_version_string = None # Bei anderen Fehlern kein Update anzeigen
        download_url = None
        update_data = None


    # Cache aktualisieren mit dem Ergebnis des aktuellen Checks
    _cached_update_status = (latest_version_string if update_data else None, update_data)
    _cache_time = time.time()
    logger.info(f"Update-Status im Cache gespeichert: {_cached_update_status}") # <-- Nutze Logging

    # Rückgabeformat: (Versionsstring oder None, Daten-Dict oder None)
    return _cached_update_status


# check_for_update_result ist wahrscheinlich nicht mehr nötig für die UI, wenn der Context Processor den Check macht.
# Wenn du es dennoch brauchst (z.B. für initiale Konsolenmeldung beim Start von desktop_app.py), kannst du es anpassen.
# def check_for_update_result():
#     # Diese Funktion wird von desktop_app.py aufgerufen. Sie sollte __version__ kennen.
#     try:
#         # Stelle sicher, dass __version__ in diesem Modul importiert ist (wie oben geschehen)
#         latest_version, _ = check_for_update(__version__) # Rufe den Haupt-Check auf
#         if latest_version:
#             logger.info(f"🔔 Update verfügbar: {latest_version}") # <-- Nutze Logging
#         else:
#             logger.info("✅ App ist aktuell.") # <-- Nutze Logging
#     except Exception as e:
#          logger.error(f"Fehler bei initialem Check in check_for_update_result: {e}", exc_info=True) # <-- Nutze Logging


def download_file(url: str, download_path: Path):
    """
    Lädt eine Datei von einer URL herunter.
    Dies ist eine einfache Version ohne Fortschrittsanzeige.
    """
    logger.info(f"Starte Download von {url} nach {download_path}...")
    try:
        # Stelle sicher, dass das Zielverzeichnis existiert
        download_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, stream=True, timeout=600) # Timeout von 10 Minuten
        response.raise_for_status() # Fehler bei schlechtem Status

        # Schreibe die Datei blockweise
        with open(download_path, "wb") as f:
            shutil.copyfileobj(response.raw, f) # Kopiere Datei-Inhalt effizient

        logger.info("Download erfolgreich abgeschlossen.")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Herunterladen der Datei von {url}: {e}", exc_info=True)
        # cleanup_path(download_path) # Versuche temporäre Datei aufzuräumen (siehe Helferfunktion unten)
        return False
    except Exception as e:
        logger.exception(f"Unerwarteter Fehler während des Downloads:")
        # cleanup_path(download_path) # Versuche temporäre Datei aufzuräumen
        return False


def install_update(update_data: dict):
    """
    Lädt das Update herunter und startet den Installationsprozess.
    Nutzt Logik aus der PySide6-Version für Windows EXE-Ersetzung (muss angepasst werden!).
    DIESE FUNKTION IST KRITISCH UND MUSS DEINEN SPEZIFISCHEN ANWENDUNGS-/INSTALLATIONSPROZESS
    SPARTEN UND DIE AKTUELLE APP BEENDEN!
    DU MUSST DIE LOGIK FÜR DOWNLOAD, START UND PROZESSENDE HIER VERVOLLSTÄNDIGEN!
    """
    if not update_data or 'download_url' not in update_data or 'version' not in update_data or 'asset_name' not in update_data:
        logger.error("InstallUpdate: Keine oder unvollständige Updatedaten erhalten.") # <-- Nutze Logging
        return

    download_url = update_data['download_url']
    new_version = update_data.get("version", "unbekannt")
    asset_name = update_data.get("asset_name", GITHUB_ASSET_NAME) # Fallback Asset Name

    # --- Schritt 1: Temporären Download-Pfad bestimmen ---
    # Verwende tempfile, um ein sicheres temporäres Verzeichnis zu erhalten.
    temp_dir = None
    download_file_path = None

    try:
        # Erstelle ein temporäres Verzeichnis für diesen Download
        # Füge PID hinzu, falls mehrere Instanzen laufen (unwahrscheinlich bei Desktop-App, aber sicher)
        temp_dir = tempfile.mkdtemp(prefix=f"FinanzAlpha_Update_{new_version}_")
        download_file_path = Path(temp_dir) / asset_name # Temporärer Pfad für die heruntergeladene Datei

    except Exception as e:
         logger.error(f"Fehler beim Erstellen des temporären Verzeichnisses oder Pfades: {e}", exc_info=True) # <-- Nutze Logging
         # cleanup_path(temp_dir) # Versuche aufzuräumen (wenn implementiert)
         # cleanup_path ist eine Helferfunktion, die unten (oder anderswo) definiert sein muss.
         return # Installation kann nicht fortgesetzt werden


    # --- Schritt 2: Datei herunterladen ---
    # Nutze die download_file Funktion (eine einfache Version ohne GUI Fortschritt)
    if not download_file(download_url, download_file_path):
        logger.error("Update-Download fehlgeschlagen. Installation abgebrochen.")
        # cleanup_path(temp_dir) # Versuche temporären Ordner aufzuräumen
        return # Download fehlgeschlagen

    logger.info("Download erfolgreich. Starte Installationsprozess...")

    # --- Schritt 3: Echte Installations-/Start-Logik hier implementieren ---
    # DIESER TEIL IST KRITISCH UND MUSS DEINE SPEZIFISCHEN ANWENDUNGS-/INSTALLATIONSPROZESS
    # WIDERGEBEN!
    # Der Pfad zur heruntergeladenen Datei ist `download_file_path`.
    # Du musst hier den Befehl oder das Skript ausführen, das dein Update startet.

    # BEISPIEL 1: Starten eines Windows Installers (.exe)
    # Wenn die heruntergeladene Datei ein Installer ist (z.B. Inno Setup, NSIS).
    # try:
    #     logger.info(f"Starte Installer: {download_file_path}")
    #     # subprocess.Popen startet einen neuen Prozess und kehrt sofort zurück.
    #     # creationflags trennen den neuen Prozess vom aktuellen (für Windows).
    #     # close_fds = True schliesst Dateihandles im Kindprozess.
    #     subprocess.Popen(
    #         [str(download_file_path)], # Der Pfad zur heruntergeladenen EXE als erstes Argument
    #         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS, # Windows-spezifisch
    #         close_fds=True
    #     )
    #     logger.info("Installer erfolgreich gestartet.")
    # except Exception as e:
    #     logger.error(f"FEHLER beim Starten des Installers {download_file_path}: {e}", exc_info=True)
    #     cleanup_path(temp_dir) # Versuche aufzuräumen
    #     return # Installation fehlgeschlagen

    # BEISPIEL 2: Windows EXE direkt ersetzen mit Batch-Skript-Trick (wie in der PySide6 Version)
    # Dies ist komplex und erfordert die Adaption und Einfügung der install_from_exe Logik aus der PySide6 Version!
    # Du müsstest hier die install_from_exe Funktion aus der PySide6-Datei kopieren, einfügen und aufrufen:
    # try:
    #     # install_from_exe muss den Pfad zur heruntergeladenen EXE bekommen
    #     # und intern die alte EXE sichern, die neue an die Stelle verschieben,
    #     # ein Batch-Skript erstellen und starten und dann sys.exit(0) aufrufen.
    #     install_from_exe(download_file_path) # Diese Funktion sollte intern sys.exit(0) aufrufen, wenn erfolgreich
    # except Exception as e:
    #     logger.error(f"FEHLER bei install_from_exe: {e}", exc_info=True)
    #     cleanup_path(temp_dir) # Versuche aufzuräumen
    #     return # Installation fehlgeschlagen

    # >>>>> WICHTIG: IMPLEMENTIERE DEINE START-LOGIK HIER <<<<<
    logger.warning(f"Installations-/Start-Logik fehlt! Heruntergeladene Datei liegt unter: {download_file_path}")
    # Entscheide dich für Beispiel 1 oder 2 (oder deine eigene Methode) und füge den Code hier ein.
    # ---------------------------------------------------------


    # --- Schritt 4: Aktuellen Prozess beenden ---
    # DIESER TEIL IST ENTSCHEIDEND!
    # Der aktuelle Python/EXE-Prozess MUSS beendet werden, nachdem der neue Prozess (Installer oder die neue EXE)
    # erfolgreich gestartet wurde, damit die Dateisperre auf der ursprünglichen EXE aufgehoben wird.
    # Wenn du BEISPIEL 2 (install_from_exe) oben verwendest, ruft diese Funktion wahrscheinlich selbst sys.exit(0) auf.
    # Wenn du BEISPIEL 1 (einfacher Installer Start) verwendest, musst du sys.exit(0) hier aufrufen.
    logger.info("InstallUpdate: Beende aktuellen Prozess...") # <-- Nutze Logging
    # sys.exit(0) # <-- ENTKOMMENTIERE DIES UND STELL SICHER, DASS DER NEUE PROZESS ERFOLGREICH GESTARTT WURDE!


    # --- Optional: Temporären Ordner aufräumen ---
    # shutil.rmtree kann fehlschlagen, wenn der Installer/neue EXE die Datei noch benutzt.
    # Der Installer sollte idealerweise selbst aufräumen oder das Aufräumen nach dem Neustart erledigen.
    # Wenn du cleanup_path als Helferfunktion implementiert hast, kannst du sie hier aufrufen:
    # cleanup_path(temp_dir) # Versuche temporären Ordner aufzuräumen


# Helferfunktion zum Aufräumen eines Pfades (Datei oder Ordner) (Optional - aus PySide6 Version adaptiert)
# Füge diese Funktion HIER oder in einem anderen Hilfsmodul ein, wenn du cleanup_path nutzen willst.
# def cleanup_path(path_to_clean: Path | str | None):
#     if not path_to_clean:
#         return
#     p = Path(path_to_clean)
#     if p.exists():
#         try:
#             if p.is_dir():
#                 # ignore_errors=True versucht zu löschen, auch wenn nicht alles geht (z.B. wegen Sperren)
#                 shutil.rmtree(p, ignore_errors=True)
#                 logger.info(f"Temporäres Verzeichnis {p} aufgeräumt (ignore_errors=True).")
#             else:
#                 p.unlink() # Versuche Datei zu löschen
#                 logger.info(f"Temporäre Datei {p} aufgeräumt.")
#         except Exception as e:
#             logger.error(f"Fehler beim Aufräumen von {p}: {e}", exc_info=True)

# Helferfunktionen für AppData Pfade (falls nicht aus core/version.py importiert und für Datei-Logging benötigt)
# Füge sie HIER oder in einem neuen Hilfsmodul ein.
# def _get_app_data_base_dir()...
# def _get_log_file_path(log_filename)...