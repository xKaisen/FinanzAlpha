from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Qt
from utils import set_unified_font

class WelcomeDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Willkommen")
        self.setFixedSize(400, 260)
        set_unified_font(self, 14)

        # Dunkler Hintergrund
        self.setStyleSheet("background-color: #2b2b2b; color: white;")

        # Accent-Style für Buttons (identisch zum Login)
        self.accent_style = """
            QPushButton {
                background-color: #1ed760; color: white;
                border:none; border-radius:4px; padding:6px; font-size:12pt;
            }
            QPushButton:hover { background-color: #42e47f; }
            QPushButton:pressed { background-color: #17b350; }
        """

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Überschrift
        welcome_label = QLabel(f"Willkommen, {username}!", self)
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("font-size:18pt; font-weight:bold;")
        layout.addWidget(welcome_label)

        # Nachricht
        message_label = QLabel(
            "Wir freuen uns, Sie wiederzusehen.\n"
            "Viel Erfolg bei der Verwaltung Ihrer Finanzen!",
            self
        )
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-size:14pt;")
        layout.addWidget(message_label)

        # Spacer
        layout.addStretch(1)

        # OK-Button
        ok_button = QPushButton("OK", self)
        ok_button.setFixedHeight(40)
        ok_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ok_button.setStyleSheet(self.accent_style)
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)
