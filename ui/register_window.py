# ui/register_window.py
import bcrypt
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QPaintEvent
from core.db import Session
from core.models import User
from utils import check_password, set_unified_font


class RegisterWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Fenstergröße & Font
        self.setFixedSize(380, 480)
        set_unified_font(self, 14)
        self.setWindowTitle("FinanzApp Registrierung")
        self.setStyleSheet("background-color: #2b2b2b;")  # Wichtig: Direkt auf Dialog setzen

        # Zentral-Widget & Layout
        layout = QVBoxLayout(self)  # Layout direkt auf Dialog setzen, nicht auf central widget
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Titel
        title = QLabel("FinanzApp Registrierung", self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20pt; font-weight:bold; color:white;")
        layout.addWidget(title)

        # Benutzername
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Benutzername")
        self.username_input.setFixedHeight(36)
        self.username_input.setStyleSheet(
            "background:#3b3b3b; color:white; border:none; padding:6px;"
        )
        layout.addWidget(self.username_input)

        # Passwort
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(36)
        self.password_input.setStyleSheet(
            "background:#3b3b3b; color:white; border:none; padding:6px;"
        )
        layout.addWidget(self.password_input)

        # Passwort wiederholen
        self.password_again = QLineEdit(self)
        self.password_again.setPlaceholderText("Passwort wiederholen")
        self.password_again.setEchoMode(QLineEdit.Password)
        self.password_again.setFixedHeight(36)
        self.password_again.setStyleSheet(
            "background:#3b3b3b; color:white; border:none; padding:6px;"
        )
        layout.addWidget(self.password_again)

        # Hinweis
        hint = QLabel(
            "Passwort muss min. 8 Zeichen lang sein,\n"
            "Groß‑ & Kleinbuchstaben, Zahl und Sonderzeichen enthalten.",
            self
        )
        hint.setStyleSheet("color:#1ed760; font-size:10pt;")  # Grüne Farbe wie auf dem Screenshot
        layout.addWidget(hint)

        # Button-Style
        self.accent_style = """
            QPushButton {
                background-color: #1ed760; color: white;
                border:none; border-radius:4px; padding:6px; font-size:11pt;
            }
            QPushButton:hover { background-color: #42e47f; }
            QPushButton:pressed { background-color: #17b350; }
        """

        # Registrieren-Button
        register_btn = QPushButton("Registrieren", self)
        register_btn.setFixedHeight(38)
        register_btn.setStyleSheet(self.accent_style)
        register_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        register_btn.clicked.connect(self.on_register)
        layout.addWidget(register_btn)

        # Abbrechen-Button
        cancel_btn = QPushButton("Abbrechen", self)
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(self.accent_style)
        cancel_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        # Footer - optional, aber würde zum Login-Fenster passen
        footer = QLabel("© 2025 xKAISEN", self)
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size:10pt; color:#cccccc;")
        layout.addWidget(footer)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        super().paintEvent(event)

    def on_register(self):
        user = self.username_input.text().strip()
        pw = self.password_input.text()
        pw2 = self.password_again.text()

        if not user or not pw:
            QMessageBox.warning(self, "Fehler", "Bitte alle Felder ausfüllen.")
            return
        if pw != pw2:
            QMessageBox.warning(self, "Fehler", "Passwörter stimmen nicht überein.")
            return

        valid, msg = check_password(pw)
        if not valid:
            QMessageBox.warning(self, "Fehler", msg)
            return

        session = Session()
        try:
            # Prüfen, ob Benutzername bereits existiert
            if session.query(User).filter(User.username.ilike(user)).first():
                QMessageBox.warning(self, "Fehler", "Benutzername existiert bereits.")
                return

            # Passwort hashen
            pwd_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

            # Neuen Benutzer anlegen
            new_user = User(username=user, password_hash=pwd_hash, is_admin=False)
            session.add(new_user)
            session.commit()

            QMessageBox.information(self, "Erfolg", "Registrierung erfolgreich.")
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Fehler bei Registrierung", f"{e}")
        finally:
            session.close()