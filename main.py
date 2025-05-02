import sys
from PySide6.QtWidgets import QApplication
import init_db       # Neue Datei zum Initialisieren der DB
from login import LoginWindow
from version import __version__  # Version importieren

if __name__ == "__main__":
    # 1. SQLite-Datenbank und Tabellen anlegen (falls noch nicht vorhanden)
    init_db.init_db()

    # 2. Anwendung starten
    app = QApplication(sys.argv)

    # 3. Login-Fenster erzeugen und Version im Titel anzeigen
    window = LoginWindow()
    window.setWindowTitle(f"FinanzAlpha v{__version__}")  # Titel mit Version
    window.show()

    # 4. Event-Loop starten
    sys.exit(app.exec())
