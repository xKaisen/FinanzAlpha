"""
constants.py – zentrale Konstanten und Pfade der FinanzApp
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_NAME = "FinanzApp"


# ──────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────
def get_base_config_dir() -> str:
    """Gibt das basis­verzeichnis für Konfigurationsdaten zurück (plattformspezifisch)."""
    system = platform.system()
    if system == "Windows":
        return os.getenv("APPDATA") or os.path.expanduser("~")
    elif system == "Darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:  # Linux / Unix
        return os.path.join(os.path.expanduser("~"), ".config")


def resource_path(rel_path: str) -> Path:
    """
    Liefert den Pfad zu eingebetteten Ressourcen (z. B. bei PyInstaller‑Builds).
    Fällt im Entwicklungsmodus einfach auf das Dateisystem zurück.
    """
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base) / rel_path


# ──────────────────────────────────────────────────────────────────────────────
# Verzeichnisstruktur
# ──────────────────────────────────────────────────────────────────────────────
CONFIG_DIR: str = os.path.join(get_base_config_dir(), APP_NAME)
os.makedirs(CONFIG_DIR, exist_ok=True)  # Sicherstellen, dass das Verzeichnis existiert

# Dateien im Config‑Verzeichnis
CREDENTIALS_FILE: str = os.path.join(CONFIG_DIR, "credentials.json")   # Zugangsdaten
LAST_VERSION_FILE: str = os.path.join(CONFIG_DIR, "last_version.json")  # Zuletzt angezeigte App‑Version

# Eingebettete Ressourcen (liegen beim Build im gleichen Package‑Ordner)
CHANGELOG_FILE: Path = resource_path("changelog.json")  # globaler Changelog aller Versionen

# Monatsnamen für UI / Reports
MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]
