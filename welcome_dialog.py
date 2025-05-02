from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from utils import set_unified_font

class WelcomeDialog(QDialog):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Willkommen")
        self.setMinimumSize(400, 200)

        # Einheitliche Schrift auf 14 pt setzen
        set_unified_font(self, 14)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        welcome_label = QLabel(f"Willkommen, {username}!")
        welcome_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(welcome_label)

        message_label = QLabel("Wir freuen uns, Sie wiederzusehen. Viel Erfolg bei der Verwaltung Ihrer Finanzen!")
        message_label.setStyleSheet("font-size: 14pt;")
        layout.addWidget(message_label)

        ok_button = QPushButton("OK")
        ok_button.setFixedHeight(40)
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)
