import sys
import os
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSpacerItem, QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette

from core.version import __version__  # Falls du das nicht brauchst, einfach entfernen

def get_changelog_path():
    base = Path(getattr(sys, "_MEIPASS", os.getcwd()))
    return (base / "ui" / "changelog.json") if (base / "ui" / "changelog.json").exists() else (base / "changelog.json")

class ChangelogDialog(QDialog):
    def __init__(self, version: str, parent=None):
        super().__init__(parent)

        # Dialog-Eigenschaften
        self.setWindowTitle(f"Changelog – v{version}")
        self.setFixedSize(600, 500)

        # Basis-Schrift
        base_font = QFont()
        base_font.setPointSize(12)
        self.setFont(base_font)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Titel
        title = QLabel(f"<center><b>Das ist neu in Version {version}</b></center>")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16pt;")
        layout.addWidget(title)

        # Textbereich
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.set_textedit_style()
        layout.addWidget(self.view, stretch=1)

        # Spacer
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Weiter-Button
        btn = QPushButton("Weiter")
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
        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(btn)
        hl.addStretch()
        layout.addLayout(hl)

        # Inhalte laden
        self.load_changelog(version)

    def set_textedit_style(self):
        # Erkennung von Dark Mode anhand Fensterfarbe
        bg_color = self.palette().color(QPalette.Window)
        is_dark = bg_color.value() < 128  # 0–255, Helligkeit

        if is_dark:
            self.view.setStyleSheet(
                "font-size: 12pt;"
                "background-color: #2b2b2b;"
                "color: #f0f0f0;"
                "padding: 10px;"
                "border: 1px solid #555;"
            )
        else:
            self.view.setStyleSheet(
                "font-size: 12pt;"
                "background-color: #fafafa;"
                "color: #000000;"
                "padding: 10px;"
                "border: 1px solid #ddd;"
            )

    def load_changelog(self, version: str):
        path = get_changelog_path()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            version_data = data.get(version)
            if not version_data:
                self.view.setPlainText("Keine Einträge für diese Version.")
                return

            sections = [
                ("features", "✨ Neue Features"),
                ("bugfixes", "🐛 Bugfixes"),
                ("known_issues", "⚠️ Bekannte Probleme"),
                ("coming_soon", "🚧🔜 COMING SOON 🔜🚧")
            ]

            lines = []
            for key, title in sections:
                entries = version_data.get(key)
                if entries:
                    lines.append(f"<b>{title}</b>")
                    lines.append("<hr>")
                    for e in entries:
                        lines.append(f"• {e}")
                    lines.append("<br>")

            self.view.setHtml("<br>".join(lines))
        except Exception as e:
            self.view.setPlainText(f"Fehler beim Laden:\n{e}")
