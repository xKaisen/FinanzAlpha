# ui/update.py
import os
import sys
import re
import logging
import tempfile
import subprocess
import requests
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMessageBox, QProgressDialog,
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QPaintEvent

from core.version import __version__

# Logging konfigurieren
logging.basicConfig(
    filename="update.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

API_LATEST = "https://api.github.com/repos/xKaisen/FinanzAlpha/releases/latest"


def fetch_latest_release(timeout=5):
    logging.info("Prüfe auf Updates…")
    r = requests.get(API_LATEST, timeout=timeout)
    r.raise_for_status()
    return r.json()


def parse_latest_version(data):
    tag = data.get("tag_name", "").lstrip("v").strip()
    logging.info(f"Neueste Version: {tag}")
    return tag


def version_tuple(v: str):
    return tuple(map(int, re.match(r"(\d+)\.(\d+)\.(\d+)", v).groups()))


def is_newer_version(latest: str, current: str) -> bool:
    try:
        return version_tuple(latest) > version_tuple(current)
    except:
        return False


def find_exe_asset(data):
    for a in data.get("assets", []):
        n = a.get("name", "")
        if n.endswith(".exe") and "Setup" not in n:
            return a["browser_download_url"], n
    return None, None


def download_with_progress(url, filename, parent=None):
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    dlg = QProgressDialog("Update wird heruntergeladen…", "Abbrechen", 0, total, parent)
    dlg.setWindowTitle("Update-Fortschritt")
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setStyleSheet(STYLE)
    dlg.show()

    done = 0
    with open(filename, "wb") as f:
        for chunk in resp.iter_content(8192):
            if dlg.wasCanceled():
                raise RuntimeError("Download abgebrochen")
            f.write(chunk)
            done += len(chunk)
            dlg.setValue(done)
            QApplication.processEvents()
    dlg.close()
    return filename


def install_from_exe(path, parent=None):
    exe = sys.executable
    bak = f"{exe}.bak"

    try:
        if os.path.exists(bak):
            os.remove(bak)
        os.replace(exe, bak)
        os.replace(path, exe)
    except Exception as e:
        logging.error(f"Fehler beim Ersetzen der EXE-Datei: {e}")
        QMessageBox.critical(parent, "Fehler", f"Update konnte nicht installiert werden:\n{e}")
        return

    script = os.path.join(tempfile.gettempdir(), f"launch_{os.getpid()}.bat")
    try:
        with open(script, "w") as f:
            f.write(f"""@echo off
timeout /t 2 >nul
start "" "{exe}"
del "%~f0"
""")
    except Exception as e:
        logging.error(f"Fehler beim Schreiben des Batch-Skripts: {e}")
        return

    try:
        subprocess.Popen(
            ["cmd.exe", "/C", script],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
    except Exception as e:
        logging.error(f"Fehler beim Starten des Batch-Skripts: {e}")
        return

    sys.exit(0)


STYLE = """
QDialog {
    background-color: #2b2b2b;
}
QLabel {
    color: white;
    font-family: "Segoe UI";
    font-size: 12pt;
}
QPushButton {
    background-color: #1ed760;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 10px;
    font-size: 12pt;
    font-family: "Segoe UI";
}
QPushButton:hover { background-color: #42e47f; }
QProgressDialog {
    background-color: #2b2b2b;
}
QProgressDialog QLabel, QProgressDialog QProgressBar {
    color: white;
    font-family: "Segoe UI";
}
QProgressBar {
    border: 1px solid #555;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #1ed760;
    border-radius: 4px;
}
"""


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update prüfen")
        self.setFixedSize(360, 200)
        self.setStyleSheet(STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        try:
            data = fetch_latest_release()
            latest = parse_latest_version(data)
        except Exception as e:
            lbl = QLabel(f"⚠️ <b>Update-Check fehlgeschlagen:</b><br>{e}", self)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: white; font-size: 14pt;")
            layout.addWidget(lbl)
            btn = QPushButton("OK", self)
            btn.clicked.connect(self.reject)
            layout.addWidget(btn)
            return

        if not is_newer_version(latest, __version__):
            lbl = QLabel(
                f"✔️ <b>Version <span style='color:#1ed760;'>{__version__}</span> ist aktuell.</b>",
                self
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: white; font-size: 16pt;")
            layout.addWidget(lbl)
            btn = QPushButton("OK", self)
            btn.clicked.connect(self.accept)
            layout.addWidget(btn)
            return

        lbl = QLabel(self)
        lbl.setText(
            "<b>Neue Version "
            f"<span style='color:#1ed760;'>{latest}</span> "
            "verfügbar!<br>"
            f"Aktuell: <span style='color:#d32f2f;'>{__version__}</span><br>"
            "Jetzt updaten?</b>"
        )
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 14pt;")
        layout.addWidget(lbl)

        hl = QHBoxLayout()
        yes = QPushButton("Jetzt updaten", self)
        no = QPushButton("Später", self)
        yes.clicked.connect(lambda: self._do_update(data))
        no.clicked.connect(self.reject)
        hl.addWidget(yes)
        hl.addWidget(no)
        layout.addLayout(hl)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        super().paintEvent(event)

    def _do_update(self, data):
        url, name = find_exe_asset(data)
        if not url:
            QMessageBox.critical(self, "Fehler", "Keine EXE-Datei gefunden.")
            return
        tmp = os.path.join(tempfile.gettempdir(), name)
        download_with_progress(url, tmp, self)
        install_from_exe(tmp, self)


def auto_check_and_prompt(parent=None):
    try:
        data = fetch_latest_release()
        latest = parse_latest_version(data)
    except:
        return

    if is_newer_version(latest, __version__) and parent:
        banner = QLabel(
            f"❗ Update verfügbar: v{latest} (aktuell: v{__version__}) ❗",
            parent
        )
        banner.setStyleSheet(
            "color:#d32f2f; font-size:14pt; padding:8px; "
            "background-color:#ffebee; border:1px solid #d32f2f; "
            "border-radius:4px;"
        )
        banner.setAlignment(Qt.AlignCenter)
        parent.centralWidget().layout().insertWidget(0, banner)


def manual_check_and_prompt(parent=None):
    dlg = UpdateDialog(parent)
    dlg.exec()
