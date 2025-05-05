import os
import json
import sys
import requests
from threading import Thread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QCheckBox, QVBoxLayout, QWidget,
    QLabel, QLineEdit, QHBoxLayout, QSizePolicy, QMessageBox, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from .login_ui import Ui_LoginWindow
from core.auth import login_user
from constants import CREDENTIALS_FILE
from ui.register_window import RegisterWindow
from ui.dashboard import Dashboard
from ui.admin_dashboard import AdminDashboard
from utils import set_unified_font
from ui.welcome_dialog import WelcomeDialog
from core.version import __version__
from ui.changelog_dialog import ChangelogDialog
from ui.full_changelog_dialog import FullChangelogDialog
from ui.update import auto_check_and_prompt, manual_check_and_prompt
from qtmodern.windows import ModernWindow

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # UI-Klasse laden
        self.ui = Ui_LoginWindow()
        self.ui.setupUi(self)

        # Fenstergröße & Font
        self.setFixedSize(380, 480)
        set_unified_font(self, 14)

        # Zentral-Widget & Layout
        central = QWidget(self)
        self.setCentralWidget(central)
        central.setStyleSheet("background-color: #2b2b2b;")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Titel
        title = QLabel("FinanzApp Login", self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20pt; font-weight:bold; color:white;")
        layout.addWidget(title)

        # Benutzername
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Benutzername")
        self.username_input.setFixedHeight(36)
        self.username_input.setStyleSheet(
            "background:#3b3b3b; color:white; border:none; padding:6px; font-size:12pt;"
        )
        self.username_input.returnPressed.connect(self.handle_login)
        layout.addWidget(self.username_input)

        # Passwort
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(36)
        self.password_input.setStyleSheet(
            "background:#3b3b3b; color:white; border:none; padding:6px; font-size:12pt;"
        )
        self.password_input.returnPressed.connect(self.handle_login)
        layout.addWidget(self.password_input)

        # Accent-Style für Buttons
        self.accent_style = """
            QPushButton {
                background-color: #1ed760; color: white;
                border:none; border-radius:4px; padding:6px; font-size:11pt;
            }
            QPushButton:hover { background-color: #42e47f; }
            QPushButton:pressed { background-color: #17b350; }
        """

        # Login-Button
        self.ui.login_button.setParent(self)
        self.ui.login_button.setFixedHeight(38)
        self.ui.login_button.setStyleSheet(self.accent_style)
        self.ui.login_button.clicked.connect(self.handle_login)
        layout.addWidget(self.ui.login_button)

        # Daten merken
        self.remember_cb = QCheckBox("Benutzernamen merken", self)
        self.remember_cb.setStyleSheet("color:white; font-size:12pt;")
        layout.addWidget(self.remember_cb)

        # Registrieren-Button
        reg_btn = QPushButton("Registrieren", self)
        reg_btn.setFixedHeight(36)
        reg_btn.setStyleSheet(self.accent_style)
        reg_btn.clicked.connect(self.open_registration)
        layout.addWidget(reg_btn)

        # Changelog + Update
        hl = QHBoxLayout()
        changelog_btn = QPushButton("Changelog", self)
        update_btn    = QPushButton("Update", self)
        for btn in (changelog_btn, update_btn):
            btn.setFixedHeight(32)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(self.accent_style)
            hl.addWidget(btn)
        layout.addLayout(hl)
        changelog_btn.clicked.connect(self.show_changelog)
        update_btn.clicked.connect(lambda: manual_check_and_prompt(self))

        # Footer
        footer = QLabel(f"© 2025 xKAISEN – v{__version__}", self)
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size:10pt; color:#cccccc;")
        layout.addWidget(footer)

        # Prefill & updates
        self.prefill()
        auto_check_and_prompt(self)
        self.dashboard_window = None

    def handle_login(self):
        user = self.username_input.text().strip()
        pwd  = self.password_input.text().strip()
        success, res = login_user(user, pwd)
        if not success:
            QMessageBox.warning(self, "Login fehlgeschlagen", res)
            return

        user_id, is_admin = res

        # Credentials schreiben/entfernen
        if self.remember_cb.isChecked() and not is_admin:
            try:
                with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({'username': user}, f)
            except:
                pass
        else:
            if os.path.exists(CREDENTIALS_FILE):
                os.remove(CREDENTIALS_FILE)

        # Willkommens-Dialog modal anzeigen
        WelcomeDialog(user, self).exec()

        # Login-Fenster schließen
        self.close()

        # Dashboard erzeugen
        dash = AdminDashboard(user_id) if is_admin else Dashboard(user_id)
        dash.login_window = self  # Setze das Login-Fenster im Dashboard

        # In ModernWindow zentriert anzeigen
        self.dashboard_window = ModernWindow(dash)
        self.dashboard_window.hide()
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        win_geo    = self.dashboard_window.frameGeometry()
        win_geo.moveCenter(screen_geo.center())
        self.dashboard_window.move(win_geo.topLeft())
        self.dashboard_window.show()

    def open_registration(self):
        RegisterWindow(self).exec()

    def show_changelog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Changelog anzeigen")
        dlg.setFixedSize(400, 260)
        set_unified_font(dlg, 12)
        dlg.setStyleSheet("background-color:#2b2b2b; color:white;")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(25,25,25,25)
        title_label = QLabel("Welchen Changelog möchtest du ansehen?", dlg)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size:14pt; font-weight:bold; margin-bottom:10px;")
        lay.addWidget(title_label)
        for text, cls in [
            ("Aktuelle Version", lambda: ChangelogDialog(__version__, dlg)),
            ("Voller Changelog", lambda: FullChangelogDialog(dlg))
        ]:
            b = QPushButton(text, dlg)
            b.setFixedHeight(40)
            b.setStyleSheet(self.accent_style)
            b.clicked.connect(lambda _, c=cls: (c().exec(), dlg.accept()))
            lay.addWidget(b)
        cancel_btn = QPushButton("Abbrechen", dlg)
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet(self.accent_style)
        cancel_btn.clicked.connect(dlg.reject)
        lay.addWidget(cancel_btn)
        dlg.exec()

    def prefill(self):
        try:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                user = json.load(f).get('username','')
                self.username_input.setText(user)
                self.remember_cb.setChecked(bool(user))
        except:
            pass

    def reset_fields(self):
        self.username_input.clear()
        self.password_input.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
