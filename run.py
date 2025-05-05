import sys
import os
import click
from threading import Thread
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication
import qtmodern.styles
import qtmodern.windows

from ui.login import LoginWindow
from core.db import init_db
from core.version import __version__
from core.changelog import show_changelog_if_needed

import requests


@click.group()
def cli():
    """FinanzAlpha CLI."""
    pass


@cli.command("init-db")
def init_db_cmd():
    """Initialisiert die Datenbank."""
    init_db()
    click.echo("🔧 Datenbank initialisiert.")


@cli.command("show-changelog")
def changelog_cmd():
    """Prüft und zeigt den Changelog-Dialog, falls eine neue Version vorliegt."""
    app = QApplication(sys.argv)
    show_changelog_if_needed()
    click.echo("🔄 Changelog-Check abgeschlossen.")


@cli.command("run-ui")
def run_ui():
    """Startet die komplette GUI-Anwendung."""
    init_db()
    app = QApplication(sys.argv)

    # Modernes, dunkles Theme anwenden
    qtmodern.styles.dark(app)

    # Zeige Changelog falls nötig
    show_changelog_if_needed()

    mode = os.getenv("APP_MODE", "offline").lower()

    def wrap_and_show(window, title_suffix):
        """Hilfsfunktion: packt Window in ModernWindow und zentriert es."""
        window.setWindowTitle(f"FinanzAlpha v{__version__} – {title_suffix}")
        modern = qtmodern.windows.ModernWindow(window)
        modern.show()
        # Nach show() Frame-Geometrie holen und zentrieren
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        win_geo = modern.frameGeometry()
        win_geo.moveCenter(screen_geo.center())
        modern.move(win_geo.topLeft())
        return modern

    if mode == "offline":
        login = LoginWindow()
        win = wrap_and_show(login, "Offline Modus")
        sys.exit(app.exec())

    elif mode == "online":
        from app import create_app
        flask_app = create_app()
        flask_app.config["OFFLINE_MODE"] = False

        def run_flask():
            flask_app.run(debug=True, port=5000, use_reloader=False)

        server_thread = Thread(target=run_flask, daemon=True)
        server_thread.start()

        login = LoginWindow()
        win = wrap_and_show(login, "Online Modus")
        sys.exit(app.exec())

    else:
        click.echo(f"Unbekannter APP_MODE '{mode}'. Bitte offline oder online.")


@cli.command("sync-transactions")
def sync_transactions():
    """Synchronisiert lokale, nicht hochgeladene Transaktionen mit der API."""
    from core.db import load_pending_transactions, mark_transactions_uploaded

    pending = load_pending_transactions()
    if not pending:
        click.echo("ℹ️ Keine ausstehenden Transaktionen.")
        return

    api_url = os.getenv("API_URL", "http://localhost:5000/api/import-transactions")
    try:
        resp = requests.post(api_url, json={"transactions": pending})
        resp.raise_for_status()
        mark_transactions_uploaded(pending)
        click.echo(f"✅ {len(pending)} Transaktionen synchronisiert.")
    except Exception as e:
        click.echo(f"❌ Sync fehlgeschlagen: {e}")


@cli.command("run-api")
def run_api():
    """Startet den Flask-API-Server (nur Web-Modus)."""
    from app import create_app
    flask_app = create_app()
    flask_app.config["OFFLINE_MODE"] = False
    flask_app.run(debug=True, port=5000, use_reloader=False)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("run-ui")
    cli()