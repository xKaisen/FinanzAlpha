# ui/login.py
import os
import json
import sys
import requests
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QCheckBox, QVBoxLayout, QWidget,
    QLabel, QLineEdit, QSpacerItem, QSizePolicy, QDialog,
    QMessageBox, QApplication
)
from PySide6.QtCore import Qt

from .login_ui import Ui_LoginWindow
from core.auth import login_user
from constants import CREDENTIALS_FILE
from .dialogs import RegistrationDialog
from .dashboard import Dashboard
from .admin_dashboard import AdminDashboard
from utils import set_unified_font
from .welcome_dialog import WelcomeDialog
from core.version import __version__
from .changelog_dialog import ChangelogDialog
from .full_changelog_dialog import FullChangelogDialog
from .update import auto_check_and_prompt, manual_check_and_prompt

TOKEN_FILE = "token.json"

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_LoginWindow()
        self.ui.setupUi(self)
        set_unified_font(self, 14)
        self.setFixedSize(750, 750)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(15)

        title = QLabel("Willkommen in der FinanzApp")
        title.setStyleSheet("font-size: 24pt; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.username_input = QLineEdit(placeholderText="Benutzername")
        self.username_input.setFixedHeight(40)
        self.username_input.returnPressed.connect(self.handle_login)
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit(placeholderText="Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)
        self.password_input.returnPressed.connect(self.handle_login)
        layout.addWidget(self.password_input)

        self.login_button = QPushButton("Login")
        self.login_button.setFixedHeight(50)
        self.login_button.setStyleSheet("font-size: 14pt;")
        self.login_button.clicked.connect(self.handle_login)
        layout.addWidget(self.login_button)

        self.remember_cb = QCheckBox("Benutzername merken")
        layout.addWidget(self.remember_cb)

        reg_btn = QPushButton("Registrieren")
        reg_btn.setFixedHeight(50)
        reg_btn.clicked.connect(self.open_registration)
        layout.addWidget(reg_btn)
        layout.addSpacerItem(QSpacerItem(0, 30, QSizePolicy.Minimum, QSizePolicy.Expanding))

        changelog_btn = QPushButton("Changelog")
        changelog_btn.setFixedHeight(50)
        changelog_btn.clicked.connect(self.show_changelog)
        layout.addWidget(changelog_btn)

        update_btn = QPushButton("Update Check")
        update_btn.setFixedHeight(50)
        update_btn.clicked.connect(lambda: manual_check_and_prompt(self))
        layout.addWidget(update_btn)

        footer = QLabel(f"Version {__version__}                © 2025 xKAISEN. Alle Rechte vorbehalten.")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        self.prefill()
        auto_check_and_prompt(self)

        # Hier behalten wir Dashboard-Instanz lebendig
        self.dashboard = None

    def handle_login(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text().strip()

        success, res = login_user(user, pwd)
        if not success:
            QMessageBox.warning(self, "Login fehlgeschlagen", res)
            return

        user_id, is_admin = res

        # Credentials merken
        if self.remember_cb.isChecked() and not is_admin:
            try:
                with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({'username': user}, f)
            except Exception as e:
                print(f"[CREDENTIALS] Fehler beim Speichern: {e}")
        else:
            self.delete_credentials_file()

        # Willkommen anzeigen
        WelcomeDialog(user, self).exec()

        # Dashboard erstellen und als Attribut speichern
        if is_admin:
            self.dashboard = AdminDashboard(user_id)
        else:
            self.dashboard = Dashboard(user_id)

        # Damit Logout wieder zum Login zurückführt
        self.dashboard.login_window = self

        # Login-Fenster ausblenden, Dashboard zeigen
        self.hide()
        self.dashboard.show()

    def open_registration(self):
        RegistrationDialog(self).exec()

    def show_changelog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Welchen Changelog möchtest du ansehen?")
        dlg.setFixedSize(400, 250)
        set_unified_font(dlg, 14)

        main_lay = QVBoxLayout(dlg)
        main_lay.setContentsMargins(20, 20, 20, 20)
        main_lay.setSpacing(20)

        label = QLabel("Welchen Changelog möchtest du ansehen?")
        label.setAlignment(Qt.AlignCenter)
        main_lay.addWidget(label)

        main_lay.addStretch()

        btn_current = QPushButton("Aktuelle Version")
        btn_current.setFixedSize(300, 40)
        btn_current.clicked.connect(lambda: (ChangelogDialog(__version__, self).exec(), dlg.accept()))

        btn_full = QPushButton("Voller Changelog")
        btn_full.setFixedSize(300, 40)
        btn_full.clicked.connect(lambda: (FullChangelogDialog(self).exec(), dlg.accept()))

        btn_lay = QVBoxLayout()
        btn_lay.setAlignment(Qt.AlignCenter)
        btn_lay.addWidget(btn_current)
        btn_lay.addWidget(btn_full)

        main_lay.addLayout(btn_lay)
        dlg.exec()

    def prefill(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.username_input.setText(data.get('username', ''))
                    self.remember_cb.setChecked(True)
            except Exception as e:
                print(f"[CREDENTIALS] Fehler beim Vorbefüllen: {e}")

    def delete_credentials_file(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                os.remove(CREDENTIALS_FILE)
            except Exception as e:
                print(f"[CREDENTIALS] Fehler beim Löschen: {e}")

    def reset_fields(self):
        self.username_input.clear()
        self.password_input.clear()
        self.remember_cb.setChecked(False)

    def save_token(self, token: str):
        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump({"token": token}, f)
        except Exception as e:
            print(f"[TOKEN] Fehler beim Speichern: {e}")

    def load_token(self):
        if Path(TOKEN_FILE).exists():
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("token")
            except Exception as e:
                print(f"[TOKEN] Fehler beim Laden: {e}")
        return None

    def delete_token(self):
        if Path(TOKEN_FILE).exists():
            try:
                Path(TOKEN_FILE).unlink()
            except Exception as e:
                print(f"[TOKEN] Fehler beim Löschen: {e}")

    def login_with_token(self, token):
        print("[TOKEN] Noch nicht implementiert")
        return False, "Noch nicht implementiert"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
