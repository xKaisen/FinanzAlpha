import sys
import os
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt


class FullChangelogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Alle Änderungen")
        self.resize(750, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("📦 Kompletter Changelog")
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)

        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setStyleSheet("font-size: 13pt;")
        layout.addWidget(self.view, stretch=1)

        btn = QPushButton("Schließen")
        # Styled wie im anderen Dialog
        btn.setFixedSize(500, 40)
        btn.setStyleSheet(
            "QPushButton {"
            "font-size: 14pt;"
            "background-color: #3a73ff;"
            "color: white;"
            "border-radius: 6px;"
            "padding: 8px;"
            "}"
            "QPushButton:hover { background-color: #5a8fff; }"
            "QPushButton:pressed { background-color: #2a5fff; }"
        )
        btn.clicked.connect(self.accept)
        # Button zentriert unten
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.load_all_versions()

    def load_all_versions(self):
        path = Path(getattr(sys, "_MEIPASS", os.path.dirname(__file__))) / "changelog.json"
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)

            sections = [
                ("features", "✨ Neue Features"),
                ("bugfixes", "🐛 Bugfixes"),
                ("known_issues", "⚠️ Bekannte Probleme"),
                ("coming_soon", "🚧🔜 COMING SOON 🔜🚧")
            ]

            lines = []
            for version, version_data in sorted(data.items(), reverse=True):
                lines.append(f"\n\n🔹 Version {version}")
                lines.append("=" * 25)
                for key, title in sections:
                    entries = version_data.get(key)
                    if entries:
                        lines.append(f"\n{title}")
                        lines.append("—" * len(title))
                        lines.extend([f"• {e}" for e in entries])

            self.view.setPlainText("\n".join(lines).strip())

        except Exception as e:
            self.view.setPlainText(f"Fehler beim Laden:\n{e}")
