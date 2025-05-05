# ui/full_changelog_dialog.py
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox,
    QScrollArea, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QFont


def resource_path(rel_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "ui" / rel_path
    return Path(__file__).parent / rel_path


class FullChangelogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alle Änderungen")
        self.resize(770, 720)

        container = QWidget(self)
        container.setObjectName("card")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # Scroll Area statt WebView
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setObjectName("scrollArea")

        # Content Widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(10)

        # Changelog-Inhalt hinzufügen
        self._add_full_changelog_content(content_layout)

        # Widget in ScrollArea setzen
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, 1)

        # Close button
        btn = QPushButton("Schließen", self)
        btn.setFixedHeight(48)
        btn.setMinimumWidth(200)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #1ed760;
                color: white;
                border-radius: 6px;
                font-size: 15pt;
                padding: 10px 0;
            }
            QPushButton:hover { filter: brightness(0.9); }
        """)
        btn.clicked.connect(self.accept)
        hl = QHBoxLayout();
        hl.addStretch();
        hl.addWidget(btn);
        hl.addStretch()
        layout.addLayout(hl)

        main = QVBoxLayout(self)
        main.addWidget(container)
        self._apply_color_scheme()

    def _add_full_changelog_content(self, layout):
        try:
            data = json.loads(resource_path("changelog.json").read_text(encoding="utf-8"))

            # Alle Versionen sortieren (neueste zuerst)
            for ver in sorted(data.keys(), reverse=True):
                # Version-Titel
                title = QLabel(f"Version {ver}")
                title.setFont(QFont("Segoe UI", 16, QFont.Bold))
                layout.addWidget(title)

                # Trennlinie
                separator = QWidget()
                separator.setFixedHeight(2)
                separator.setStyleSheet("background-color: #555555;")
                layout.addWidget(separator)

                # Sektionen
                for key, heading in [
                    ("features", "✨ Neue Features"),
                    ("bugfixes", "🐛 Bugfixes"),
                    ("known_issues", "⚠️ Bekannte Probleme"),
                    ("coming_soon", "🚧🔜 COMING SOON 🔜🚧"),
                ]:
                    items = data[ver].get(key)
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
                        spacer.setFixedHeight(10)
                        layout.addWidget(spacer)

                # Abstand zwischen Versionen
                version_spacer = QWidget()
                version_spacer.setFixedHeight(30)
                layout.addWidget(version_spacer)

            # Fügt Platz am Ende hinzu, damit alles gut lesbar ist
            layout.addStretch()

        except Exception as e:
            error_label = QLabel(f"Fehler beim Laden: {str(e)}")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        super().paintEvent(event)

    def _apply_color_scheme(self):
        pal = self.palette()
        is_dark = pal.color(QPalette.Window).lightness() < 128

        if is_dark:
            bg_color = "#1e1e1e"
            fg_color = "#f0f0f0"
            scroll_bg = "#2a2a2a"
            scroll_handle = "#4d4d4d"
            scroll_handle_hover = "#1ed760"  # Grün im Hover-Zustand
        else:
            bg_color = "#f5f5f5"
            fg_color = "#111111"
            scroll_bg = "#e0e0e0"
            scroll_handle = "#c0c0c0"
            scroll_handle_hover = "#1ed760"  # Grün im Hover-Zustand

        self.setStyleSheet(f"""
            QWidget#card {{ 
                background-color: {bg_color}; 
                border-radius: 8px; 
            }}
            QScrollArea#scrollArea {{ 
                background-color: {bg_color}; 
                border: none;
            }}
            QWidget {{ 
                background-color: {bg_color}; 
                color: {fg_color};
            }}
            QLabel {{
                color: {fg_color};
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