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
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QSpacerItem, QSizePolicy
)

from PySide6.QtCore import Qt
from core.version import __version__

# Configure logging for update operations
logging.basicConfig(
    filename='update.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# GitHub Releases API endpoint
API_LATEST = "https://api.github.com/repos/xKaisen/FinanzAlpha/releases/latest"


def fetch_latest_release(timeout=5):
    try:
        logging.info("Prüfe auf Updates...")
        r = requests.get(API_LATEST, timeout=timeout)
        r.raise_for_status()
        logging.info(f"API-Antwort: {r.json()}")
        return r.json()
    except Exception as e:
        logging.error(f"Update-Check fehlgeschlagen: {e}")
        raise


def parse_latest_version(data):
    latest_version = data.get("tag_name", "").lstrip("v").strip()
    logging.info(f"Neueste Version: {latest_version}")
    return latest_version


def find_exe_asset(data):
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".exe") and "Setup" not in name:
            logging.info(f"EXE-Asset gefunden: {name}")
            return asset["browser_download_url"], name
    logging.warning("Keine passende EXE-Datei gefunden")
    return None, None


def version_tuple(v: str):
    return tuple(map(int, re.match(r"(\d+)\.(\d+)\.(\d+)", v).groups()))


def is_newer_version(latest: str, current: str) -> bool:
    return version_tuple(latest) > version_tuple(current)


def download_with_progress(url, filename, parent=None):
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        progress = QProgressDialog(
            "Update wird heruntergeladen...",
            "Abbrechen", 0, total_size, parent
        )
        progress.setWindowTitle("Update-Fortschritt")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        downloaded = 0
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if progress.wasCanceled():
                    raise RuntimeError("Download abgebrochen")
                f.write(chunk)
                downloaded += len(chunk)
                progress.setValue(downloaded)
                QApplication.processEvents()

        progress.close()
        logging.info(f"Download abgeschlossen: {filename}")
        return filename

    except Exception as e:
        logging.error(f"Download fehlgeschlagen: {e}")
        raise


def install_from_exe(new_exe_path, parent=None):
    try:
        current_exe = sys.executable
        backup_path = f"{current_exe}.bak"

        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(current_exe, backup_path)
        logging.info(f"Backup der alten EXE erstellt: {backup_path}")

        os.rename(new_exe_path, current_exe)
        logging.info(f"Neue EXE an {current_exe} verschoben")

        start_script = os.path.join(tempfile.gettempdir(), f"launch_{os.getpid()}.bat")
        with open(start_script, "w", encoding="utf-8") as f:
            f.write(f'''@echo off
timeout /t 4 /nobreak >nul
start "" "{current_exe}"
del "%~f0"
''')

        subprocess.Popen(
            ["cmd.exe", "/C", start_script],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )

        logging.info("Starter-Batch gestartet. App wird beendet.")
        sys.exit(0)

    except Exception as e:
        logging.error(f"EXE-Update fehlgeschlagen: {e}")
        show_error(parent, "Update-Fehler", f"EXE konnte nicht ersetzt werden:\n{e}")


def show_error(parent, title, message):
    try:
        QMessageBox.critical(parent, title, message)
        logging.error(f"{title}: {message}")
    except Exception:
        print(f"{title}: {message}")


def _do_update(parent):
    try:
        data = fetch_latest_release()
        url, name = find_exe_asset(data)
        if not url:
            raise RuntimeError("Keine EXE-Datei im Release gefunden")

        tmp_path = os.path.join(tempfile.gettempdir(), name)
        download_with_progress(url, tmp_path, parent)

        reply = QMessageBox.question(
            parent,
            "Update starten",
            "Die neue Version wurde heruntergeladen. App neu starten?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            install_from_exe(tmp_path, parent)

    except Exception as e:
        show_error(parent, "Update fehlgeschlagen", str(e))


def check_for_update():
    try:
        data = fetch_latest_release()
        latest = parse_latest_version(data)
        if is_newer_version(latest, __version__):
            return latest
    except Exception as e:
        logging.warning(f"Update-Check fehlgeschlagen: {e}")
    return None


def auto_check_and_prompt(parent=None):
    try:
        data = fetch_latest_release()
        latest = parse_latest_version(data)

        if is_newer_version(latest, __version__):
            logging.info(f"Neue Version verfügbar: {latest}")  # Debug-Logging
            existing = parent.findChild(QLabel, "updateBanner") if parent else None
            if existing:
                existing.setText(
                    f"❗ Update verfügbar: v{latest} (aktuell: v{__version__})❗\n"
                    "❗Update Check' um zu installieren❗"
                )
                existing.setVisible(True)
                return

            banner = QLabel(
                f"❗ Update verfügbar: v{latest} (aktuell: v{__version__})❗\n"
                "❗Click 'Update Check' to installieren❗"
            )
            banner.setObjectName("updateBanner")
            banner.setStyleSheet(
                """
                color: #d32f2f;
                font-size: 15pt;
                padding: 15px;
                border: 1px solid #d32f2f;
                border-radius: 5px;
                background-color: #ffebee;
                font-weight: bold;
                """
            )
            banner.setAlignment(Qt.AlignCenter)
            banner.setWordWrap(True)

            if parent and parent.centralWidget():
                layout = parent.centralWidget().layout()
                layout.insertWidget(0, banner)
                logging.info("Banner wurde zum Layout hinzugefügt")

    except Exception as e:
        logging.warning(f"Automatischer Update-Check (Banner) fehlgeschlagen: {e}")


def manual_check_and_prompt(parent=None):
    try:
        latest = check_for_update()
        if not latest:
            dlg = QDialog(parent)
            dlg.setWindowTitle("Kein Update verfügbar")
            dlg.setFixedSize(500, 200)

            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(20, 20, 20, 20)
            lay.setSpacing(15)

            label = QLabel(
                f"<center>✔️ Version {__version__} ist aktuell.✔️<br>"
                "Es sind keine Updates verfügbar.</center>"
            )
            label.setStyleSheet("font-size: 14pt;")
            label.setAlignment(Qt.AlignCenter)
            lay.addWidget(label)

            lay.addStretch()

            ok_btn = QPushButton("OK")
            ok_btn.setFixedSize(500, 40)
            ok_btn.setStyleSheet(
                "font-size: 14pt; background-color: #3a73ff; color: white; border-radius: 6px;"
            )
            ok_btn.clicked.connect(dlg.accept)
            btn_lay = QHBoxLayout()
            btn_lay.addStretch()
            btn_lay.addWidget(ok_btn)
            btn_lay.addStretch()
            lay.addLayout(btn_lay)

            dlg.exec()
            return

        dlg = QDialog(parent)
        dlg.setWindowTitle("Update verfügbar")
        dlg.setFixedSize(500, 300)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)

        label = QLabel(
            f"<center><b>NEUE Version <span style='color: #2ECC71; text-decoration: underline;'>"
            f"{latest}</span> ist verfügbar!</b><br>"
            f"Aktuell Version: <b style='color: #d32f2f;'>{__version__}</b><br>"
            "Möchten Sie jetzt updaten?</center>"
        )
        label.setStyleSheet(
            "color: palette(text); font-size: 18pt; font-weight: normal;"
        )
        label.setAlignment(Qt.AlignCenter)
        lay.addWidget(label)

        lay.addStretch()

        yes_btn = QPushButton("Jetzt updaten")
        no_btn = QPushButton("Später")

        style = """
            QPushButton {
                font-size: 14pt;
                background-color: #BA55D3;
                color: white;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #B388B3;
            }
            QPushButton:pressed {
                background-color: #9E6FA1;
            }
        """

        yes_btn.setStyleSheet(style)
        no_btn.setStyleSheet(style)

        yes_btn.setFixedSize(450, 40)
        no_btn.setFixedSize(450, 40)

        yes_btn.clicked.connect(lambda: (_do_update(parent), dlg.accept()))
        no_btn.clicked.connect(dlg.reject)

        btn_lay2 = QVBoxLayout()
        btn_lay2.setAlignment(Qt.AlignCenter)
        btn_lay2.addWidget(yes_btn)
        btn_lay2.addWidget(no_btn)
        lay.addLayout(btn_lay2)

        dlg.exec()
    except Exception as e:
        logging.warning(f"Fehler im manuellen Update-Dialog: {e}")
