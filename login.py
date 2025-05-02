import os, json
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QMessageBox, QCheckBox, QVBoxLayout,
    QWidget, QLabel, QLineEdit
)
from PySide6.QtCore import Qt
from ui.login_ui import Ui_LoginWindow
from auth import login_user
from constants import CONFIG_FILE
from dialogs import RegistrationDialog
from dashboard import Dashboard
from admin_dashboard import AdminDashboard
from utils import set_unified_font
from welcome_dialog import WelcomeDialog


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # UI laden und Grundlayout vorbereiten
        self.ui = Ui_LoginWindow()
        self.ui.setupUi(self)

        set_unified_font(self, 14)
        self.resize(600, 400)

        # ── eigenes GUI-Layout ersetzen (wenn ui-Datei leer) ──────────
        central = QWidget(self)
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(50, 50, 50, 50)
        vbox.setSpacing(20)

        title = QLabel("Willkommen zur FinanzApp")
        title.setStyleSheet("font-size: 24pt; font-weight: bold;")
        vbox.addWidget(title)

        self.username_input = QLineEdit(placeholderText="Benutzername")
        self.username_input.setFixedHeight(40)
        self.password_input = QLineEdit(placeholderText="Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)
        vbox.addWidget(self.username_input)
        vbox.addWidget(self.password_input)

        self.login_button = QPushButton("Login")
        self.login_button.setFixedHeight(40)
        self.login_button.clicked.connect(self.handle_login)
        vbox.addWidget(self.login_button)

        self.remember_cb = QCheckBox("Daten merken")
        vbox.addWidget(self.remember_cb)

        reg_btn = QPushButton("Registrieren")
        reg_btn.setFixedHeight(40)
        reg_btn.clicked.connect(self.open_registration)
        vbox.addWidget(reg_btn)

        # gespeicherte Zugangsdaten vorbefüllen
        self.prefill()

    # ------------------------------------------------------------------
    def prefill(self):
        """Nur Nicht-Admin-Nutzer werden vorbefüllt."""
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.username_input.setText(data.get("username", ""))
            self.password_input.setText(data.get("password", ""))
            self.remember_cb.setChecked(True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def handle_login(self):
        user = self.username_input.text().strip()
        pwd  = self.password_input.text().strip()

        success, res = login_user(user, pwd)
        if not success:
            QMessageBox.warning(self, "Fehler", res)
            return

        user_id, is_admin = res

        # ── Speicherlogik ──────────────────────────────────────────────
        if is_admin:
            # Admin-Logins NIEMALS speichern
            self.remember_cb.setChecked(False)
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
        else:
            if self.remember_cb.isChecked():
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({"username": user, "password": pwd}, f)
            elif os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)

        # Begrüßungsdialog
        WelcomeDialog(user, self).exec()

        # Dashboard öffnen
        self.open_dashboard(user_id, is_admin)

    # ------------------------------------------------------------------
    def open_registration(self):
        RegistrationDialog(self).exec()

    def open_dashboard(self, user_id, is_admin):
        """Login-Fenster schließen und Dashboard offen halten."""
        self.close()
        # Referenz in Instanz-Attribut speichern ⇒ Fenster bleibt erhalten
        if is_admin:
            self.dashboard = AdminDashboard(user_id)
        else:
            self.dashboard = Dashboard(user_id)
        self.dashboard.show()

    # Enter-Taste als Login
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.handle_login()
