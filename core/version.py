# core/version.py – Version-Management
from __future__ import annotations

import json
import os
from pathlib import Path
import datetime
import logging

# >>>>> PASSE DIESE KONSTANTEN AN <<<<<
FIRMENNAME = 'DeineFirma'
ANWENDUNGSNAME = 'FinanzAlpha'
# >>>>> ENDE ANPASSUNG <<<<<

__version__ = "1.3.0"


def _get_app_data_base_dir() -> Path:
    """
    Ermittelt das App‑Verzeichnis:
    - Unter Windows: %LOCALAPPDATA%\<FIRMENNAME>\<ANWENDUNGSNAME>
    - Unter Unix:   $XDG_DATA_HOME/<FIRMENNAME>/<ANWENDUNGSNAME> oder ~/.local/share/...
    """
    if os.name == 'nt':
        # Windows
        local_app_data = os.getenv('LOCALAPPDATA')
        if not local_app_data:
            logging.error("Umgebungsvariable LOCALAPPDATA ist nicht gesetzt. Kann AppData-Pfad nicht bestimmen.")
            raise EnvironmentError("LOCALAPPDATA nicht gesetzt.")
        base = Path(local_app_data)
    else:
        # Unix‑Fallback
        xdg = os.getenv('XDG_DATA_HOME')
        if xdg:
            base = Path(xdg)
        else:
            base = Path.home() / '.local' / 'share'

    app_data_dir = base / FIRMENNAME / ANWENDUNGSNAME
    try:
        app_data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.error(f"Fehler beim Erstellen des Verzeichnisses {app_data_dir}: {e}")
        raise

    return app_data_dir


def _get_last_version_file_path() -> Path:
    env_path = os.getenv("LAST_VERSION_FILE")
    if env_path:
        logging.info(f"Verwende LAST_VERSION_FILE aus Umgebungsvariable: {env_path}")
        return Path(env_path)
    else:
        try:
            app_data_dir = _get_app_data_base_dir()
            return app_data_dir / "last_version.json"
        except Exception:
            logging.error("Kann Standard AppData‑Pfad für Version-Datei nicht bestimmen.")
            raise


try:
    _LAST_VERSION_FILE_PATH = _get_last_version_file_path()
except Exception as e:
    logging.critical(f"Kritischer Fehler beim Bestimmen des Version-Datei Pfades: {e}")
    _LAST_VERSION_FILE_PATH = None


class VersionService:
    @staticmethod
    def get_last_version() -> str | None:
        if _LAST_VERSION_FILE_PATH is None:
            return None
        if not _LAST_VERSION_FILE_PATH.exists():
            return None
        try:
            with open(_LAST_VERSION_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("last_version")
        except Exception as e:
            logging.error(f"Fehler beim Lesen der Version‑Datei {_LAST_VERSION_FILE_PATH}: {e}")
            return None

    @staticmethod
    def set_last_version(v: str) -> None:
        if _LAST_VERSION_FILE_PATH is None:
            return
        try:
            data = {
                "last_version": str(v),
                "timestamp": datetime.datetime.now().isoformat()
            }
            with open(_LAST_VERSION_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logging.info(f"Version gespeichert: {v} nach {_LAST_VERSION_FILE_PATH}")
        except Exception as e:
            logging.error(f"Fehler beim Schreiben der Version nach {_LAST_VERSION_FILE_PATH}: {e}")
