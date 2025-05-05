# ui/changelog_dialog.py
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox,
    QScrollArea, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QFont


def resource_path(rel_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "ui" / rel_path
    return Path(__file__).parent / rel_path


class ChangelogDialog(QDialog):
    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Changelog – v{version}")
        self.setFixedSize(620, 540)

        # Hauptlayout
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Container als "Karte"
        container = QWidget(self)
        container.setObjectName("card")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # Scroll Area mit modernem Styling
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setObjectName("scrollArea")

        # Content Widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(10)

        # Changelog-Inhalt hinzufügen
        self._add_changelog_content(content_layout, version)

        # Widget in ScrollArea setzen
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, 1)

        # Close button
        btn = QPushButton("Schließen", self)
        btn.setFixedHeight(40)
        btn.setFixedWidth(180)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #1ed760;
                color: white;
                border-radius: 6px;
                font-size: 14pt;
                padding: 8px 16px;
            }
            QPushButton:hover { 
                background-color: #1ed760CC;
            }
            QPushButton:pressed { 
                background-color: #1ed76099;
            }
        """)
        btn.clicked.connect(self.accept)

        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(btn)
        hl.addStretch()
        layout.addLayout(hl)

        main.addWidget(container)

        # Immer dunkles Design verwenden
        self._apply_dark_theme()

    def _add_changelog_content(self, layout, version):
        try:
            data = json.loads(resource_path("changelog.json").read_text(encoding="utf-8"))
            ver = data.get(version, {})

            # Titel
            title = QLabel(f"Version {version}")
            title.setFont(QFont("Segoe UI", 16, QFont.Bold))
            layout.addWidget(title)

            # Trennlinie unter dem Titel
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("background-color: #555555;")
            layout.addWidget(separator)

            # Sektionen
            for key, heading in [
                ("features", "✨ Neue Features"),
                ("bugfixes", "🐛 Bugfixes"),
                ("known_issues", "⚠️ Bekannte Probleme"),
                ("coming_soon", "🚧🔜 COMING SOON 🔜🚧"),
            ]:
                items = ver.get(key)
                if items:
                    # Sektions-Überschrift
                    section_title = QLabel(heading)
                    section_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
                    layout.addWidget(section_title)

                    # Einträge
                    for item in items:
                        entry = QLabel(f"• {item}")
                        entry.setWordWrap(True)
                        entry.setTextFormat(Qt.RichText)
                        entry.setFont(QFont("Segoe UI", 12))
                        layout.addWidget(entry)

                    # Abstand nach jeder Sektion
                    spacer = QWidget()
                    spacer.setFixedHeight(15)
                    layout.addWidget(spacer)

            # Wenn keine Einträge vorhanden sind
            if not ver:
                no_entries = QLabel("Keine Einträge.")
                no_entries.setFont(QFont("Segoe UI", 12))
                layout.addWidget(no_entries)

            # Fügt Platz am Ende hinzu damit alles gut lesbar ist
            layout.addStretch()

        except Exception as e:
            error_label = QLabel(f"Fehler beim Laden: {str(e)}")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        super().paintEvent(event)

    def _apply_dark_theme(self):
        # Immer dunkles Design wie im Login-Fenster
        bg_color = "#2b2b2b"  # Login-Hintergrund
        card_color = "#2b2b2b"
        text_color = "#f0f0f0"
        scroll_bg = "#3b3b3b"
        scroll_handle = "#4d4d4d"
        scroll_handle_hover = "#1ed760"  # Grün im Hover-Zustand

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QWidget#card {{ 
                background-color: {card_color}; 
                border-radius: 8px; 
            }}
            QScrollArea#scrollArea {{ 
                background-color: {card_color}; 
                border: none;
            }}
            QWidget {{ 
                background-color: {card_color}; 
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}

            /* Scrollbar-Styling */
            QScrollBar:vertical {{
                background: {scroll_bg};
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                min-height: 30px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {scroll_handle_hover};
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}

            /* Horizontalen Scrollbalken auch stylen */
            QScrollBar:horizontal {{
                background: {scroll_bg};
                height: 12px;
                margin: 0px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal {{
                background: {scroll_handle};
                min-width: 30px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background: {scroll_handle_hover};
            }}

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """)