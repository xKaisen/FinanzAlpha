# core/changelog.py
from core.version import __version__, VersionService
from ui.changelog_dialog import ChangelogDialog


def show_changelog_if_needed(parent=None):
    """
    Zeigt einmalig den Changelog-Dialog an, wenn die Version geändert wurde.
    """
    last = VersionService.get_last_version()
    if last != __version__:
        # Neue Version erkannt
        print(f"[DEBUG] Neue Version erkannt: {last} -> {__version__}")
        # ChangelogDialog aus dem UI aufrufen
        ChangelogDialog(__version__, parent).exec()
        # Version speichern
        VersionService.set_last_version(__version__)
        print(f"[DEBUG] Version gespeichert: {__version__}")
