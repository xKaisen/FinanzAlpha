# ui/update.py
import os
import sys
import re
import logging
import tempfile
import subprocess
import requests
from pathlib import Path  # pathlib importieren
import datetime # Für Zeitstempel im Log oder bei Downloads/Installation

# Importe von PySide6
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QProgressDialog,
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer # QTimer kann nützlich sein
from PySide6.QtGui import QFont, QPainter, QPaintEvent, QGuiApplication # QGuiApplication für Bildschirmgeo

# Import der Anwendungsversion
from core.version import __version__ # __version__ kommt weiterhin von core/version.py


# >>>>> PASSE DIESE KONSTANTEN AN <<<<<
# Konfiguration für AppData Pfad und Log-Datei
# Diese Namen MÜSSEN mit denen in core/version.py übereinstimmen!
FIRMENNAME = 'IhreFirma' # <--- MUSS MIT core/version.py ÜBEREINSTIMMEN
ANWENDUNGSNAME = 'FinanzAlpha' # <--- MUSS MIT core/version.py ÜBEREINSTIMMEN
# >>>>> ENDE ANPASSUNG <<<<<

LOG_DATEINAME = "update.log"


# --- Hilfsfunktionen für Pfade im Benutzerprofil ---

def _get_app_data_base_dir() -> Path:
    """
    Ermittelt den anwendungsspezifischen Basis-Pfad in %LOCALAPPDATA%
    und erstellt das Verzeichnis, falls es nicht existiert.
    Wirf einen Fehler, wenn LOCALAPPDATA nicht verfügbar ist.
    (Diese Funktion ist eine Kopie aus core/version.py oder könnte aus einem gemeinsamen Hilfsmodul importiert werden)
    """
    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        raise EnvironmentError("Umgebungsvariable LOCALAPPDATA ist nicht gesetzt.")

    app_data_dir = Path(local_app_data) / FIRMENNAME / ANWENDUNGSNAME

    try:
        app_data_dir.mkdir(parents=True, exist_ok=True)
        # print(f"[DEBUG] Sichergestellt, dass AppData-Basisverzeichnis existiert: {app_data_dir}") # Debug
    except OSError as e:
        print(f"Fehler beim Erstellen des Anwendungsverzeichnisses {app_data_dir}: {e}")
        raise

    return app_data_dir

def _get_log_file_path(log_filename: str) -> Path:
    """
    Ermittelt den Pfad für eine Log-Datei im Unterverzeichnis 'Logs'
    innerhalb des anwendungsspezifischen AppData-Ordners.
    Erstellt das Log-Verzeichnis, falls nötig.
    Bietet einen Fallback-Pfad im AppData-Basisordner, falls das Logs-Verzeichnis nicht erstellt werden kann.
    """
    app_data_dir = _get_app_data_base_dir()
    log_dir = app_data_dir / "Logs" # Ein Unterordner für Logs

    try:
        # Erstelle das Log-Verzeichnis und Elternverzeichnisse, falls nötig
        log_dir.mkdir(parents=True, exist_ok=True)
        # print(f"[DEBUG] Sichergestellt, dass Log-Verzeichnis existiert: {log_dir}") # Debug
        return log_dir / log_filename
    except OSError as e:
        print(f"Fehler beim Erstellen des Log-Verzeichnisses {log_dir}: {e}")
        # Fallback: Log-Datei direkt im AppData-Basisordner ablegen
        print(f"Versuche Fallback-Log-Pfad im AppData-Basisordner: {app_data_dir / log_filename}") # Debug
        return app_data_dir / log_filename
        # Oder werfen Sie hier einen Fehler, wenn Logging kritisch ist: raise


# --- Logging konfigurieren ---
# Konfiguriere das Root-Logger, um zu vermeiden, dass es von anderen Bibliotheken überschrieben wird
# Überprüfen, ob Handler bereits konfiguriert sind, um Doppel-Logging zu vermeiden
if not logging.root.handlers:
    try:
        # Ermitteln Sie den Pfad für die update.log Datei
        log_file_full_path = _get_log_file_path(LOG_DATEINAME)

        # Konfigurieren Sie das Logging, um in die ermittelte Datei zu schreiben
        logging.basicConfig(
            filename=log_file_full_path, # Verwenden Sie den ermittelten Pfad
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            encoding='utf-8' # Sicherstellen, dass Umlaute etc. korrekt geloggt werden
        )
        logging.info("-" * 60) # Trennlinie im Log
        logging.info(f"Anwendung gestartet. Version: {__version__}")
        logging.info(f"Logging in Datei konfiguriert: {log_file_full_path}") # Bestätigungs-Log

    except Exception as e:
        # Fallback-Logging auf die Konsole, falls Datei-Logging fehlschlägt
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        logging.error(f"FEHLER: Konfiguration des Datei-Loggings fehlgeschlagen: {e}. Logge zur Konsole.")
        logging.info("-" * 60) # Trennlinie im Log (auch auf Konsole)
        logging.info(f"Anwendung gestartet. Version: {__version__}")

# --- Update Check Logik ---
API_LATEST = "https://api.github.com/repos/xKaisen/FinanzAlpha/releases/latest"


def fetch_latest_release(timeout=10): # Timeout erhöht
    logging.info(f"Prüfe auf Updates von {API_LATEST}...")
    try:
        r = requests.get(API_LATEST, timeout=timeout)
        r.raise_for_status() # Wirft HTTPError für schlechte Antworten (4xx oder 5xx)
        logging.info("Update-Check erfolgreich.")
        return r.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Fehler beim Abrufen des neuesten Releases: {e}")
        raise # Wirf den Fehler erneut, damit der Aufrufer ihn behandeln kann


def parse_latest_version(data):
    tag = data.get("tag_name", "").lstrip("v").strip() # Entfernt führendes 'v'
    logging.info(f"Neueste Version auf GitHub: '{tag}'")
    return tag


def version_tuple(v: str):
    """Konvertiert eine Versionszeichenkette (z.B. '1.2.3') in ein Tupel von Integern."""
    # Stellt sicher, dass die Version das Format major.minor.patch hat
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if not match:
        logging.warning(f"Ungültiges Versionsformat: '{v}'. Kann nicht verglichen werden.")
        # Wirf hier einen Fehler, der oben abgefangen wird
        raise ValueError(f"Ungültiges Versionsformat: '{v}'")
    return tuple(map(int, match.groups()))


def is_newer_version(latest: str, current: str) -> bool:
    """Vergleicht zwei Versionszeichenketten."""
    try:
        # Prüfe, ob beide Versionen gültig sind, bevor verglichen wird
        latest_t = version_tuple(latest)
        current_t = version_tuple(current)
        is_newer = latest_t > current_t
        logging.info(f"Version Vergleich: Aktuell '{current}' ({current_t}), Neueste '{latest}' ({latest_t}). Neuere Version verfügbar: {is_newer}")
        return is_newer
    except ValueError:
        # Fehler bei version_tuple wird hier abgefangen und führt dazu, dass keine neue Version erkannt wird
        logging.error(f"Fehler beim Vergleichen der Versionen '{latest}' und '{current}' aufgrund ungültigen Formats.")
        return False
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Vergleichen der Versionen '{latest}' und '{current}': {e}")
        return False


def find_exe_asset(data):
    """Sucht nach dem passenden EXE-Asset im GitHub Release."""
    logging.info("Suche nach .exe Asset im Release...")
    for a in data.get("assets", []):
        n = a.get("name", "")
        # Suche nach einer .exe-Datei, die NICHT "Setup" im Namen hat (nimmt die portable EXE an)
        if n.lower().endswith(".exe") and "setup" not in n.lower():
            logging.info(f"Gefundenes Asset: {n} ({a.get('browser_download_url')})")
            return a.get("browser_download_url"), n
    logging.warning("Kein geeignetes .exe Asset im Release gefunden.")
    return None, None


def download_with_progress(url, filename, parent=None):
    """Lädt eine Datei von einer URL herunter und zeigt einen Fortschrittsdialog."""
    logging.info(f"Starte Download von {url} nach tempfile...")
    temp_dir = Path(tempfile.gettempdir())
    download_path = temp_dir / filename
    logging.info(f"Temporärer Download-Pfad: {download_path}")

    try:
        resp = requests.get(url, stream=True, timeout=60) # Timeout erhöht
        resp.raise_for_status() # Wirft HTTPError

        total = int(resp.headers.get("content-length", 0))
        logging.info(f"Download Größe: {total} Bytes")

        dlg = QProgressDialog("Update wird heruntergeladen…", "Abbrechen", 0, total, parent)
        dlg.setWindowTitle("Update-Fortschritt")
        dlg.setWindowModality(Qt.WindowModal)
        #dlg.setAutoClose(False) # Dialog soll offen bleiben, bis wir ihn explizit schließen
        dlg.setStyleSheet(STYLE) # STYLE muss definiert sein
        dlg.show()

        done = 0
        # Stelle sicher, dass die Datei neu erstellt wird (kein Anhängen)
        with open(download_path, "wb") as f:
            for chunk in resp.iter_content(8192): # Kleinere Blöcke für feinere Fortschrittsanzeige
                if dlg.wasCanceled():
                    logging.warning("Download vom Benutzer abgebrochen.")
                    # Temporäre Datei löschen
                    if download_path.exists():
                         try:
                             download_path.unlink()
                             logging.info(f"Temporäre Datei gelöscht: {download_path}")
                         except Exception as unlink_e:
                             logging.error(f"Fehler beim Löschen der temporären Datei {download_path}: {unlink_e}")
                    dlg.close() # Dialog schließen
                    raise RuntimeError("Download abgebrochen") # Wirf eine Exception

                f.write(chunk)
                done += len(chunk)
                # Aktualisiere den Fortschritt im GUI-Thread
                QApplication.processEvents() # Ermöglicht GUI-Updates
                dlg.setValue(done)


        # Download abgeschlossen
        dlg.setValue(total) # Setze Fortschritt auf 100%
        # Warte kurz, damit der Benutzer 100% sieht
        QTimer.singleShot(500, dlg.close) # Schließe Dialog nach 500ms

        logging.info("Download erfolgreich abgeschlossen.")
        return download_path # Gib den vollständigen Pfad der heruntergeladenen Datei zurück

    except requests.exceptions.RequestException as e:
        logging.error(f"Fehler beim Download: {e}")
        if parent:
            QMessageBox.critical(parent, "Download Fehler", f"Fehler beim Herunterladen des Updates:\n{e}")
        return None # Download fehlgeschlagen
    except RuntimeError as e:
         logging.info(f"Download abgebrochen: {e}")
         # Die Nachricht wird bereits in der Dialog-Logik behandelt, muss hier nicht als MessageBox
         # QMessageBox.warning(parent, "Download abgebrochen", "Der Update-Download wurde abgebrochen.")
         return None # Download abgebrochen
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Download: {e}", exc_info=True)
        if parent:
            QMessageBox.critical(parent, "Download Fehler", f"Ein unerwarteter Fehler ist beim Download aufgetreten:\n{e}")
        return None


def install_from_exe(downloaded_exe_path: Path, parent=None):
    """
    Ersetzt die aktuell laufende EXE durch die heruntergeladene EXE
    und startet die neue EXE über ein temporäres Batch-Skript neu.
    Diese Funktion beendet die aktuelle Anwendung erfolgreich, wenn die Installation gestartet wurde.
    """
    logging.info(f"Starte Installation von {downloaded_exe_path}...")
    # sys.executable ist der Pfad zur aktuell laufenden Python-EXE (wenn gebündelt)
    current_exe = Path(sys.executable)
    backup_exe = current_exe.with_suffix(".exe.bak") # Backup-Pfad ist direkt neben der aktuellen EXE


    try:
        # 1. Alte Backup-Datei löschen, falls vorhanden
        if backup_exe.exists():
            logging.info(f"Lösche alte Sicherung: {backup_exe}")
            try:
                backup_exe.unlink() # Datei löschen
                logging.info("Alte Sicherung erfolgreich gelöscht.")
            except Exception as e:
                 logging.warning(f"Konnte alte Sicherung {backup_exe} nicht löschen: {e}") # Logge Warnung, fahre fort

        # 2. Aktuelle EXE sichern (verschieben)
        logging.info(f"Sichere aktuelle EXE: {current_exe} -> {backup_exe}")
        # os.replace ist atomar (oder simuliert es auf Windows), wenn möglich
        # Es verschiebt die Datei. Wenn erfolgreich, ist die Originaldatei an der Backup-Position.
        os.replace(current_exe, backup_exe)
        logging.info("Aktuelle EXE erfolgreich gesichert.")

        # 3. Neue EXE an die Stelle der alten verschieben
        logging.info(f"Ersetze EXE: Verschiebe {downloaded_exe_path} nach {current_exe}")
        # os.replace versucht, downloaded_exe_path nach current_exe zu verschieben/umbenennen.
        # Wenn current_exe (obwohl die alte dort weg ist) immer noch durch etwas anderes blockiert ist,
        # oder es Berechtigungsprobleme gibt, schlägt dies fehl.
        os.replace(downloaded_exe_path, current_exe) # <--- HIER SOLL DIE NEUE EXE DIE ALTE ERSETZEN
        logging.info("Neue EXE erfolgreich an Position der alten verschoben.")

        # Temporäre heruntergeladene Datei sollte nun gelöscht sein,
        # da os.replace sie "bewegt" hat. Prüfen und ggf. explizit löschen.
        if downloaded_exe_path.exists():
             logging.warning(f"Heruntergeladene Datei {downloaded_exe_path} existiert noch nach os.replace.")
             try:
                 downloaded_exe_path.unlink() # Versuche sie explizit zu löschen
                 logging.info("Temporäre Datei explizit gelöscht.")
             except Exception as e:
                  logging.error(f"Konnte temporäre Datei {downloaded_exe_path} nicht löschen: {e}")


    except Exception as e:
        logging.error(f"FEHLER während der Installation (Ersetzen der EXE): {e}", exc_info=True) # Loggt auch Traceback
        # Wenn das Ersetzen fehlschlägt, kann die App nicht korrekt gestartet werden.
        # Wir informieren den Benutzer und beenden die App trotzdem, damit er ggf. manuell eingreifen kann.
        if parent:
             QMessageBox.critical(parent, "Installationsfehler", f"Update konnte nicht installiert werden:\n{e}\nBitte versuchen Sie es erneut oder starten Sie die App manuell neu.")
        # Wir fahren fort, das Neustart-Skript zu erstellen und die App zu beenden,
        # auch wenn die Ersetzung fehlgeschlagen ist. Dies könnte helfen, Dateisperren zu lösen.
        # Die neue App wird wahrscheinlich nicht starten oder die alte (falsche) Version starten,
        # aber es ist besser als die App hängen zu lassen.


    # --- Schritt 4-6: Neustart über Batch-Skript und App beenden ---
    # Diese Schritte werden auch ausgeführt, wenn das Ersetzen fehlgeschlagen ist,
    # da wir die App beenden MÜSSEN, damit die neue EXE gestartet werden kann und Sperren gelöst werden.

    # 4. Batch-Skript erstellen, um die neue EXE zu starten und sich selbst zu löschen
    # Der Name enthält die PID, um Konflikte zu vermeiden, falls mehrere Instanzen laufen (unwahrscheinlich)
    script_path = Path(tempfile.gettempdir()) / f"launch_{os.getpid()}_{int(datetime.datetime.now().timestamp())}.bat"
    logging.info(f"Schreibe Neustart-Skript: {script_path}")

    # WICHTIG: Das Skript bekommt den Pfad der *neuen* EXE (die erfolgreich/fehlerhaft an die ursprüngliche Stelle verschoben wurde) als Argument %1
    script_content = f"""@echo off
rem Batch-Skript zur Durchführung des App-Neustarts nach Update.
rem Erhaltenen Pfad der neuen EXE (die jetzt an der alten Stelle liegt)
set "NEW_EXE_PATH=%%1"
rem Pfad zur Backup-Datei (sollte direkt neben der neuen EXE liegen)
set "BACKUP_PATH=%%1.bak"

rem --- Wartezeit ---
rem Warte kurz, um sicherzustellen, dass die alte App vollständig beendet ist und die Dateisperre aufgehoben ist.
rem timeout wartet die angegebene Zeit. /t ist die Zeit in Sekunden. >nul unterdrückt die Ausgabe.
timeout /t 2 >nul
rem Zusätzliche kurze Wartezeit mit ping, kann bei race conditions helfen.
ping 127.0.0.1 -n 2 > nul rem Warte eine extra Sekunde (n=2 bedeutet 1 Sekunde Wartezeit)

rem --- Starte die neue EXE ---
rem "start "" " verhindert Probleme mit Pfaden, die Leerzeichen enthalten, und startet in einem neuen Fenster/Konsole (aber wir haben CREATE_NO_WINDOW gesetzt).
rem "%NEW_EXE_PATH%" ist der volle Pfad zur neuen ausführbaren Datei.
logging.info("Skript: Starte neue EXE...")
start "" "%NEW_EXE_PATH%"
logging.info("Skript: Neue EXE gestartet.")

rem --- Aufräumen ---
rem Versuche, die Sicherungsdatei (.bak) leise zu löschen.
rem > nul leitet die Standardausgabe ins Nichts. 2>&1 leitet die Fehlerausgabe (2) zur Standardausgabe (1) um (die ebenfalls ins Nichts geleitet wird).
logging.info("Skript: Versuche Backup-Datei zu löschen...")
del "%BACKUP_PATH%" > nul 2>&1
logging.info("Skript: Versuch Backup-Datei zu löschen abgeschlossen.")

rem Lösche dieses Batch-Skript, nachdem es seine Aufgabe erfüllt hat.
logging.info("Skript: Lösche mich selbst...")
del "%~f0"
logging.info("Skript: Skript beendet.")
""" # End of script_content


    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        logging.info(f"Neustart-Skript {script_path} erfolgreich geschrieben.")
    except Exception as e:
        logging.error(f"FEHLER beim Schreiben des Batch-Skripts {script_path}: {e}")
        # Ein Fehler hier ist kritisch, da der Neustart fehlschlägt.
        # Wir fahren fort, die App zu beenden, der Benutzer muss ggf. manuell starten.
        if parent:
             QMessageBox.critical(parent, "Installationsfehler", f"Konnte Neustart-Skript nicht schreiben:\n{e}\nBitte App manuell neu starten.")
        # Kein 'return', fahren fort zur App-Beendigung.


    # 5. Batch-Skript starten
    try:
        logging.info(f"Starte Neustart-Skript: {script_path} mit Argument: {current_exe}")
        # subprocess.Popen startet einen neuen Prozess.
        # "/C" führt den Befehl aus und beendet cmd.
        # creationflags machen den Prozess unabhängig vom Elternprozess (DETACHED_PROCESS)
        # und ohne eigenes Konsolenfenster (CREATE_NO_WINDOW).
        # Wir übergeben den Pfad der NEUEN (jetzt an alter Position liegenden) EXE als Argument (%1 im Batch).
        subprocess.Popen(
            ["cmd.exe", "/C", str(script_path), str(current_exe)], # script_path ist %0, current_exe ist %1 im Batch
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True # Stellt sicher, dass Dateihandles geschlossen werden, kann bei Sperren helfen
        )
        logging.info("Neustart-Skript erfolgreich gestartet.")
    except Exception as e:
        logging.error(f"FEHLER beim Starten des Batch-Skripts {script_path}: {e}")
        # Loggen, aber App trotzdem beenden.
        if parent:
             QMessageBox.critical(parent, "Installationsfehler", f"Konnte Neustart-Skript nicht starten:\n{e}\nBitte App manuell neu starten.")


    # 6. Aktuelle App beenden
    # Dies ist ENTSCHEIDEND, damit die Dateisperre auf der ursprünglichen EXE (und jetzt der neuen EXE an der Position) aufgehoben wird
    # und das Batch-Skript die neue EXE starten und die Sicherung löschen kann.
    logging.info("Beende aktuelle App-Instanz (sys.exit(0)).")
    sys.exit(0)


# --- GUI Style ---
STYLE = """
QDialog {
    background-color: #2b2b2b; /* Dunkler Hintergrund */
    border: 1px solid #555; /* Optionaler Rand */
    border-radius: 8px; /* Abgerundete Ecken */
}
QLabel {
    color: white; /* Weiße Schrift */
    font-family: "Segoe UI", sans-serif; /* Moderne Schriftart */
    font-size: 12pt;
    padding: 4px; /* Innenabstand */
}
QPushButton {
    background-color: #1ed760; /* Spotify-Grün */
    color: white;
    border: none;
    border-radius: 6px; /* Leicht abgerundet */
    padding: 12px 20px; /* Innenabstand */
    font-size: 13pt;
    font-family: "Segoe UI", sans-serif;
    min-width: 80px; /* Mindestbreite */
}
QPushButton:hover {
    background-color: #42e47f; /* Helleres Grün beim Hover */
}
QPushButton:pressed {
    background-color: #1aa34a; /* Dunkleres Grün beim Drücken */
}
/* Style für den 'Später' Button, falls gewünscht */
QPushButton#LaterButton { /* Setzen Sie objectName("LaterButton") in der UI */
    background-color: #555;
}
QPushButton#LaterButton:hover {
    background-color: #666;
}
QPushButton#LaterButton:pressed {
    background-color: #444;
}

QProgressDialog {
    background-color: #2b2b2b;
    border: 1px solid #555;
    border-radius: 8px;
}
QProgressDialog QLabel, QProgressDialog QProgressBar {
    color: white;
    font-family: "Segoe UI", sans-serif;
    font-size: 12pt;
}
QProgressBar {
    border: 1px solid #555;
    border-radius: 4px;
    text-align: center; /* Zentriert den Text */
    color: white; /* Farbe des Prozenttextes */
    background-color: #444; /* Hintergrundfarbe des Balkens */
}
QProgressBar::chunk {
    background-color: #1ed760; /* Fortschrittsfarbe */
    border-radius: 4px; /* Muss gleich dem der ProgressBar sein */
}
"""


class UpdateDialog(QDialog):
    """
    Dialog zur Anzeige des Update-Status und Durchführung des Updates.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update prüfen")
        self.setFixedSize(400, 250) # Etwas größer für mehr Inhalt
        self.setStyleSheet(STYLE)

        # Fenster zentrieren (optional, kann auch in der main.py geschehen)
        # Benötigt QGuiApplication
        if parent:
             screen_geo = QGuiApplication.primaryScreen().availableGeometry()
             win_geo = self.frameGeometry()
             win_geo.moveCenter(screen_geo.center())
             self.move(win_geo.topLeft())


        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30) # Mehr Innenabstand
        layout.setSpacing(15) # Größerer Abstand zwischen Widgets

        # Label für Status oder Info
        self.status_label = QLabel("Prüfe auf Updates...", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: white; font-size: 14pt;")
        layout.addWidget(self.status_label)

        # Buttons für Aktionen (Update, Später, OK) - werden je nach Status hinzugefügt
        self.button_layout = QHBoxLayout()
        self.update_button = QPushButton("Jetzt updaten", self)
        self.later_button = QPushButton("Später", self)
        self.ok_button = QPushButton("OK", self) # Für "aktuell" oder "Fehler" Zustand

        # Object Names setzen, falls im STYLE verwendet (z.B. #LaterButton)
        self.update_button.setObjectName("UpdateButton")
        self.later_button.setObjectName("LaterButton")
        self.ok_button.setObjectName("OkButton")


        self.update_button.clicked.connect(self._do_update)
        self.later_button.clicked.connect(self.reject) # Später -> Dialog schließen mit reject
        self.ok_button.clicked.connect(self.accept) # OK -> Dialog schließen mit accept

        # Alle Buttons zunächst verstecken
        self.update_button.hide()
        self.later_button.hide()
        self.ok_button.hide()

        self.button_layout.addWidget(self.update_button)
        self.button_layout.addWidget(self.later_button)
        self.button_layout.addWidget(self.ok_button)

        layout.addLayout(self.button_layout)

        # Starte den Check-Prozess
        # Verwenden Sie singleShot, um den Check asynchron zu starten,
        # damit das Fenster sich erst aufbauen und zeigen kann.
        QTimer.singleShot(10, self.check_for_update)


    def check_for_update(self):
        """Führt den Update-Check durch und aktualisiert das Dialog-Layout."""
        logging.info("UpdateDialog: Starte Check for update...")
        self.status_label.setText("Prüfe auf Updates...")
        # Verstecke alle Buttons während des Checks
        self.update_button.hide()
        self.later_button.hide()
        self.ok_button.hide()


        try:
            data = fetch_latest_release()
            latest = parse_latest_version(data)

            # Speichere die Release-Daten für den Download-Schritt
            self._latest_release_data = data

            if is_newer_version(latest, __version__):
                # Neuere Version verfügbar
                logging.info(f"UpdateDialog: Neuere Version {latest} verfügbar.")
                self.status_label.setText(
                    f"<b>Neue Version <span style='color:#1ed760;'>{latest}</span> verfügbar!</b><br>"
                    f"Aktuell installiert: <span style='color:#d32f2f;'>{__version__}</span><br>"
                    "Möchten Sie jetzt aktualisieren?"
                )
                self.status_label.setStyleSheet("color: white; font-size: 15pt;")
                self.update_button.show()
                self.later_button.show()
                # OK Button bleibt versteckt
            else:
                # App ist aktuell
                logging.info(f"UpdateDialog: App Version {__version__} ist aktuell.")
                self.status_label.setText(
                    f"✔️ <b>Ihre Version <span style='color:#1ed760;'>{__version__}</span> ist aktuell.</b>"
                )
                self.status_label.setStyleSheet("color: white; font-size: 16pt;")
                self.ok_button.show() # Nur OK Button anzeigen
                # Update und Später Buttons bleiben versteckt

        except Exception as e:
            # Fehler beim Update-Check
            logging.error(f"UpdateDialog: Update-Check Prozess fehlgeschlagen: {e}", exc_info=True)
            self.status_label.setText(
                f"⚠️ <b>Update-Check fehlgeschlagen:</b><br>{e}<br>Bitte versuchen Sie es später erneut."
            )
            self.status_label.setStyleSheet("color: #ffeb3b; font-size: 14pt;") # Gelbe Warnfarbe
            self.ok_button.show() # Nur OK Button anzeigen
            # Update und Später Buttons bleiben versteckt

    def paintEvent(self, event: QPaintEvent):
        """Standard PaintEvent für QDialog."""
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        super().paintEvent(event)

    def _do_update(self):
        """Startet den Download und die Installation."""
        logging.info("UpdateDialog: Benutzer klickte 'Jetzt updaten'.")
        # Verstecke die Buttons, da der Prozess startet
        self.update_button.hide()
        self.later_button.hide()
        self.ok_button.hide()
        self.status_label.setText("Vorbereitung für den Download...") # Status aktualisieren

        # Holen Sie die Release-Daten, die beim Check gespeichert wurden
        data = getattr(self, '_latest_release_data', None)
        if not data:
            logging.error("UpdateDialog: Update-Daten nicht verfügbar beim Starten des Downloads.")
            QMessageBox.critical(self, "Fehler", "Fehler: Update-Informationen fehlen.")
            self.reject() # Dialog schließen
            return

        # Finden Sie das EXE Asset
        url, name = find_exe_asset(data)
        if not url or not name:
            logging.error("UpdateDialog: Kein geeignetes .exe Asset im Release gefunden.")
            QMessageBox.critical(self, "Fehler", "Keine passende EXE-Datei für das Update gefunden.")
            self.reject() # Dialog schließen
            return

        # Temporäre Datei herunterladen
        # download_with_progress gibt den vollständigen Pfad zurück oder None bei Fehler/Abbruch
        downloaded_file_path = download_with_progress(url, name, self)

        if downloaded_file_path:
            # Download war erfolgreich, jetzt installieren
            self.status_label.setText("Update wird installiert...") # Status aktualisieren
            # install_from_exe wird die App beenden und die neue Version starten, wenn erfolgreich
            # Wenn install_from_exe einen Fehler hat, der kein sys.exit(0) auslöst,
            # kehrt die Funktion zurück, und die Fehlermeldung wurde bereits angezeigt.
            install_from_exe(downloaded_file_path, self)

            # Wenn install_from_exe erfolgreich war, wird sys.exit(0) aufgerufen,
            # und der Code hier wird nicht erreicht.
            # Wenn install_from_exe fehlgeschlagen ist und zurückgekehrt ist:
            logging.warning("UpdateDialog: install_from_exe kehrte zurück (Fehler?). Schließe Dialog.")
            self.reject() # Dialog schließen

        else:
            # Download fehlgeschlagen oder abgebrochen (Nachricht bereits in download_with_progress)
            logging.info("UpdateDialog: Download fehlgeschlagen oder abgebrochen.")
            self.reject() # Dialog schließen


# --- Funktionen für den Aufruf außerhalb des Dialogs ---

def auto_check_and_prompt(parent=None):
    """
    Führt einen automatischen Check durch und zeigt ein Banner im Parent-Widget,
    wenn ein Update verfügbar ist. Startet keinen modalen Dialog.
    """
    logging.info("Automatischer Update-Check gestartet (im Hintergrund).")
    try:
        data = fetch_latest_release()
        latest = parse_latest_version(data)

        # Prüfen, ob eine neuere Version verfügbar ist
        if is_newer_version(latest, __version__):
            logging.info(f"Neuere Version {latest} für automatische Benachrichtigung gefunden.")
            # Wenn ein Parent-Widget (z.B. Hauptfenster) gegeben ist und es ein Layout hat
            if parent and hasattr(parent, 'centralWidget') and parent.centralWidget() and parent.centralWidget().layout():
                banner_text = (
                    f"❗ Update verfügbar: v{latest} ❗\n"  # Erste Zeile mit Newline
                    f"(aktuell: v{__version__})"  # Zweite Zeile
                )
                banner = QLabel(
                    banner_text,  # Verwenden Sie die Variable
                    parent.centralWidget()  # Setze das zentrale Widget als Parent
                )
                banner.setStyleSheet(
                    "color:#d32f2f; font-size:14pt; padding:8px; "
                    "background-color:#ffebee; border:1px solid #d32f2f; "
                    "border-radius:4px; margin-bottom: 8px;" # Abstand nach unten
                )
                banner.setAlignment(Qt.AlignCenter)
                banner.setWordWrap(True) # Wichtig für kleinere Fenster
                # Füge das Banner am Anfang des Layouts des zentralen Widgets ein
                parent.centralWidget().layout().insertWidget(0, banner)
                logging.info("Update-Banner in UI eingefügt.")
            else:
                 logging.warning("Kann Update-Banner nicht anzeigen: Parent oder dessen Layout ist nicht verfügbar.")
        else:
            logging.info("Keine neuere Version für automatischen Check gefunden oder App ist bereits aktuell.")

    except Exception as e:
        # Fehler beim automatischen Check werden nur geloggt, nicht als Dialog angezeigt
        logging.error(f"Automatischer Update-Check fehlgeschlagen: {e}", exc_info=True)


def manual_check_and_prompt(parent=None):
    """
    Startet den UpdateDialog für einen manuellen Check und ggf. Installation.
    Dies blockiert, bis der Dialog geschlossen wird.
    """
    logging.info("Manueller Update-Check über Dialog gestartet.")
    # Der Dialog führt den Check selbst aus, wenn er erstellt und gezeigt wird
    dlg = UpdateDialog(parent)
    # exec() startet den Dialog modal und blockiert, bis er geschlossen wird.
    dlg.exec()
    logging.info("Manueller Update-Check Dialog beendet.")

# --- Beispiel zur Verwendung (in Ihrer main.py aufrufen) ---
if __name__ == '__main__':
    # Dieses Beispiel zeigt, wie der manuelle Check funktioniert.
    # In Ihrer eigentlichen App würden Sie manual_check_and_prompt() oder auto_check_and_prompt()
    # von Ihrer Hauptanwendung aus aufrufen.

    # QApplication muss immer zuerst erstellt werden
    app = QApplication(sys.argv)

    # Dummy-Hauptfenster nur für das Beispiel, um parent=main_win nutzen zu können
    from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel as QLabel_QtWidgets # Alias, da QLabel im Dialog schon genutzt wird
    main_win = QMainWindow()
    main_win.setWindowTitle("Hauptanwendung (Dummy)")
    central_widget = QWidget()
    main_win.setCentralWidget(central_widget)
    central_layout = QVBoxLayout(central_widget)
    central_layout.addWidget(QLabel_QtWidgets(f"Hauptfenster der App v{__version__}"))
    central_layout.setAlignment(Qt.AlignCenter)

    # Fügen Sie hier weitere Widgets zu Ihrem Hauptlayout hinzu

    main_win.show()

    # Beispiel: Manuellen Check starten (z.B. über einen Menüpunkt "Nach Updates suchen")
    # manual_check_and_prompt(main_win) # Oder einfach manual_check_and_prompt() wenn kein Parent nötig ist


    # Beispiel: Automatischen Check beim Starten der App (im Hintergrund)
    # auto_check_and_prompt(main_win)


    # Führen Sie hier Ihre Hauptanwendungs-Logik weiter aus.
    # Wenn manual_check_and_prompt() aufgerufen wurde, kehrt es erst zurück, wenn der Dialog geschlossen ist.
    # Wenn auto_check_and_prompt() aufgerufen wurde, kehrt es sofort zurück.

    # Starten Sie den Qt Event Loop
    sys.exit(app.exec())