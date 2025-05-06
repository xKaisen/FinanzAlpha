# core/version.py – Version-Management
from __future__ import annotations

import json
import os
from pathlib import Path  # pathlib importieren
import datetime # Für Zeitstempel beim Speichern
import logging # Importiere Logging auch hier

# Konfiguriere Logging für dieses Modul (optional, kann von root logger übernommen werden)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)


# >>>>> PASSE DIESE KONSTANTEN AN <<<<<
# Konfiguration für AppData Pfad
# Diese Namen werden als Unterverzeichnisse in AppData verwendet
FIRMENNAME = 'DeineFirma' # <--- BITTE HIER ANPASSEN
ANWENDUNGSNAME = 'FinanzAlpha' # <--- BITTE HIER ANPASSEN
# >>>>> ENDE ANPASSUNG <<<<<


# Aktuelle Version der App; hier bei jedem Release anpassen
# Dies sollte der Version entsprechen, die in deiner GitHub-Release-Tag steht (z.B. "0.0.5" für Tag "v0.0.5")
__version__ = "1.2.0" # Beispielversion - Bei jedem Build/Release anpassen!


def _get_app_data_base_dir() -> Path:
    """
    Ermittelt den anwendungsspezifischen Basis-Pfad in %LOCALAPPDATA%
    und erstellt das Verzeichnis, falls es nicht existiert.
    Wirf einen Fehler, wenn LOCALAPPDATA nicht verfügbar ist (was unter Windows unwahrscheinlich ist).
    """
    # Holt den Pfad zu LOCALAPPDATA aus den Umgebungsvariablen
    local_app_data = os.getenv('LOCALAPPDATA')

    if not local_app_data:
        # Dies sollte auf einem Standard-Windows-System nicht passieren.
        # Wenn es doch passiert, deutet das auf ein Problem hin.
        # Statt einfach None zurückzugeben oder in das Home-Verzeichnis zu schreiben (was unüblich ist),
        # werfen wir hier einen Fehler, da die App ohne diesen Pfad nicht korrekt arbeiten kann.
        logging.error("Umgebungsvariable LOCALAPPDATA ist nicht gesetzt. Kann AppData-Pfad nicht bestimmen.")
        raise EnvironmentError("Umgebungsvariable LOCALAPPDATA ist nicht gesetzt.")

    # Konstruiert den vollen Pfad: ...\AppData\Local\<FIRMENNAME>\<ANWENDUNGSNAME>
    app_data_dir = Path(local_app_data) / FIRMENNAME / ANWENDUNGSNAME

    try:
        # Erstellt das Verzeichnis und alle notwendigen Elternverzeichnisse, falls sie nicht existieren.
        # exist_ok=True verhindert einen Fehler, wenn das Verzeichnis bereits existiert.
        app_data_dir.mkdir(parents=True, exist_ok=True)
        # logging.debug(f"Sichergestellt, dass Verzeichnis existiert: {app_data_dir}") # Debug-Ausgabe
    except OSError as e:
        # Fehler beim Erstellen des Verzeichnisses (z.B. keine Berechtigung, voller Speicher)
        logging.error(f"Fehler beim Erstellen des Anwendungsverzeichnisses {app_data_dir}: {e}")
        raise # Den Fehler weitergeben

    return app_data_dir

def _get_last_version_file_path() -> Path:
    """
    Bestimmt den finalen Pfad zur last_version.json.
    Prüft zuerst die Umgebungsvariable LAST_VERSION_FILE, fällt dann auf den AppData-Pfad zurück.
    """
    # Zuerst prüfen, ob eine Umgebungsvariable gesetzt ist (z.B. für Tests oder spezielle Setups)
    env_path = os.getenv("LAST_VERSION_FILE")
    if env_path:
        # Wenn die Umgebungsvariable gesetzt ist, verwenden wir diesen Pfad.
        # ACHTUNG: Das Verzeichnis für diesen Pfad wird hier NICHT automatisch erstellt.
        # Der Aufrufer (oder der Benutzer, der die Env-Variable setzt) muss sicherstellen,
        # dass das Verzeichnis existiert, falls er die Env-Variable nutzt.
        logging.info(f"Verwende LAST_VERSION_FILE aus Umgebungsvariable: {env_path}") # Debug-Ausgabe
        return Path(env_path)
    else:
        # Standardfall: Verwenden Sie den Pfad im LOCALAPPDATA-Ordner.
        # Das notwendige Verzeichnis wird von _get_app_data_base_dir() erstellt.
        try:
            app_data_dir = _get_app_data_base_dir()
            default_path = app_data_dir / "last_version.json"
            # logging.debug(f"Verwende Standard AppData LAST_VERSION_FILE: {default_path}") # Debug-Ausgabe
            return default_path
        except EnvironmentError:
            # Wenn _get_app_data_base_dir fehlschlägt
            logging.error("Kann Standard AppData-Pfad für Version-Datei nicht bestimmen.")
            # Wir könnten hier None zurückgeben, aber das würde bei get/set_last_version zu Fehlern führen.
            # Besser: Fehler werfen oder einen Fallback-Pfad (z.B. temporär) verwenden,
            # abhängig davon, wie kritisch das Speichern der Version ist.
            # Für diesen Fall werfen wir erneut den Fehler oder geben einen unsicheren Pfad zurück.
            # Nehmen wir der Einfachheit halber an, ein Fehler bei _get_app_data_base_dir
            # bedeutet, dass wir nicht sicher speichern können.
            raise


# Bestimmen Sie den finalen Pfad zur Version-Datei, wenn das Modul geladen wird.
# Dieser Pfad ist nun ein Path-Objekt von pathlib. Wenn _get_last_version_file_path fehlschlägt,
# wird hier eine Exception geworfen, was den App-Start verhindert, wenn das Versions-Management kritisch ist.
try:
    _LAST_VERSION_FILE_PATH = _get_last_version_file_path()
except Exception as e:
    logging.critical(f"Kritischer Fehler beim Bestimmen des Version-Datei Pfades: {e}")
    _LAST_VERSION_FILE_PATH = None # Setze auf None, um Fehler bei get/set zu ermöglichen


class VersionService:
    """Dienstklasse zur Verwaltung der zuletzt gestarteten Version."""

    @staticmethod
    def get_last_version() -> str | None:
        """
        Gibt die zuletzt gespeicherte Version zurück, oder None, wenn noch keine vorhanden ist
        oder ein Fehler auftritt.
        """
        if _LAST_VERSION_FILE_PATH is None:
            logging.error("Version-Datei Pfad konnte nicht bestimmt werden. Kann letzte Version nicht lesen.")
            return None

        # Verwenden Sie den bereits ermittelten Path-Objekt
        if not _LAST_VERSION_FILE_PATH.exists():
            # logging.debug(f"Version-Datei existiert nicht: {_LAST_VERSION_FILE_PATH}") # Debug-Ausgabe
            return None # Wenn die Datei nicht existiert

        try:
            # Öffnen und Lesen der JSON-Datei
            with open(_LAST_VERSION_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Lesen Sie den Wert des Schlüssels "last_version"
                last_version = data.get("last_version")
                # logging.debug(f"Gelesene letzte Version: {last_version} von {_LAST_VERSION_FILE_PATH}") # Debug-Ausgabe
                return last_version
        except (IOError, json.JSONDecodeError) as e:
             # Behandeln von Fehlern beim Datei-IO oder beim Parsen von JSON
             logging.error(f"Fehler beim Lesen oder Parsen der Version-Datei {_LAST_VERSION_FILE_PATH}: {e}")
             return None # Bei Fehlern geben wir None zurück
        except Exception as e:
             logging.exception(f"Unerwarteter Fehler beim Lesen der Version-Datei {_LAST_VERSION_FILE_PATH}:")
             return None

    @staticmethod
    def set_last_version(v: str) -> None:
        """
        Speichert die übergebene Version in die Datei, zusammen mit einem Zeitstempel.
        """
        if _LAST_VERSION_FILE_PATH is None:
            logging.error("Version-Datei Pfad konnte nicht bestimmt werden. Kann Version nicht speichern.")
            return

        try:
            # Datenstruktur für die JSON-Datei
            data = {
                "last_version": str(v), # Stelle sicher, dass es als String gespeichert wird
                "timestamp": datetime.datetime.now().isoformat() # Aktuellen Zeitstempel hinzufügen
            }

            # Öffnen und Schreiben der JSON-Datei
            # Verwende 'w' für Schreiben, 'r' für Lesen. Wenn die Datei nicht existiert, wird sie erstellt.
            with open(_LAST_VERSION_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4) # indent=4 macht die JSON-Datei besser lesbar
            logging.info(f"Version gespeichert: {v} nach {_LAST_VERSION_FILE_PATH}")

        except IOError as e:
            # Fehler beim Schreiben der Datei (z.B. keine Berechtigung)
            logging.error(f"Fehler beim Schreiben der Version nach {_LAST_VERSION_FILE_PATH}: {e}")
        except Exception as e:
             # Andere unerwartete Fehler (z.B. beim JSON-Dump)
             logging.exception(f"Unerwarteter Fehler beim Speichern der Version:")