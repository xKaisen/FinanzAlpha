# core/version.py
import json
import os

# Aktuelle Version eurer App; hier anpassen
__version__ = "1.0.1"

# Pfad zur Datei, in der die letzte angezeigte Version gespeichert wird
LAST_VERSION_FILE = os.environ.get("LAST_VERSION_FILE", "last_version.json")

class VersionService:
    @staticmethod
    def get_last_version() -> str | None:
        """
        Gibt die zuletzt gespeicherte Version zurück, oder None, wenn noch keine vorhanden ist.
        """
        if not os.path.exists(LAST_VERSION_FILE):
            return None
        try:
            with open(LAST_VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("last_version")
        except Exception:
            return None

    @staticmethod
    def set_last_version(v: str) -> None:
        """
        Speichert die übergebene Version in die Datei.
        """
        try:
            with open(LAST_VERSION_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_version": v}, f)
        except Exception as e:
            print(f"[DEBUG] Fehler beim Schreiben der Version: {e}")
