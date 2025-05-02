# admin_dashboard.py
"""Admin-Dashboard für Benutzer‑, Vorschlags‑ und Passwortverwaltung.
    – Nutzung von Qt‑Themen‑Icons mit robusten Fallbacks
    – Schutz vor Entfernen des letzten Admins, Passwort‑Reset etc.
"""

import sys
import functools
import bcrypt

from PySide6.QtWidgets import (
    QApplication,
    QDialog, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QWidget, QHBoxLayout, QPushButton,
    QMessageBox, QInputDialog, QCheckBox, QLineEdit, QStyle,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QGuiApplication

from db import get_db_connection
from utils import set_unified_font


class AdminDashboard(QDialog):
    """Zentrales Admin‑Fenster: Vorschläge, Benutzerverwaltung, Passwort‑Reset & Logout."""

    def __init__(self, user_id: int, parent=None):
        super().__init__(parent)
        set_unified_font(self, 14)
        self.setWindowTitle("Admin‑Dashboard")
        self.resize(900, 640)

        # ---------- Admin‑Prüfung ----------
        if not self._is_admin(user_id):
            QMessageBox.critical(self, "Zugriff verweigert", "Du besitzt keine Admin‑Rechte.")
            self.close()
            return

        main = QVBoxLayout(self)

        # ---------- obere Leiste mit Logout ----------
        top = QHBoxLayout()
        top.addStretch()
        btn_logout = QPushButton("Abmelden")
        btn_logout.clicked.connect(self._logout)
        top.addWidget(btn_logout)
        main.addLayout(top)

        # ---------- Tabs ----------
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        # Tabellen
        self.tbl_desc = self._create_table(["Text", "Aktion"])
        self.tbl_usage = self._create_table(["Text", "Aktion"])
        self.tbl_users = self._create_table(
            ["ID", "Benutzername", "Admin", "Aktion", "PW ändern"], stretch_col=1
        )

        self.tabs.addTab(self.tbl_desc, "Name / Firma")
        self.tabs.addTab(self.tbl_usage, "Verwendungszweck")
        self.tabs.addTab(self.tbl_users, "Benutzer")

        self._refresh_all()

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    def _logout(self):
        from login import LoginWindow

        self.login_win = LoginWindow()  # Referenz halten, sonst GC
        self.login_win.show()
        self.close()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    def _create_table(self, headers, stretch_col=0):
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        for c in range(len(headers)):
            mode = QHeaderView.Stretch if c == stretch_col else QHeaderView.ResizeToContents
            tbl.horizontalHeader().setSectionResizeMode(c, mode)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        return tbl

    def _is_admin(self, uid: int) -> bool:
        with get_db_connection() as c:
            cur = c.cursor()
            cur.execute("SELECT is_admin FROM users WHERE id=?", (uid,))
            row = cur.fetchone()
        return bool(row and row[0])

    # ------------------------------------------------------------------
    # Daten laden
    # ------------------------------------------------------------------
    def _refresh_all(self):
        self._load_suggestions(self.tbl_desc, "description")
        self._load_suggestions(self.tbl_usage, "usage")
        self._load_users()

    def _load_suggestions(self, tbl: QTableWidget, column: str):
        with get_db_connection() as c:
            rows = c.execute(
                f"SELECT DISTINCT {column} FROM fix_suggestions ORDER BY {column}"
            ).fetchall()

        tbl.setRowCount(0)
        for (text,) in rows:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem(text))
            tbl.setCellWidget(
                r,
                1,
                self._action_widget(
                    functools.partial(self._edit_suggestion, column, text),
                    functools.partial(self._delete_suggestion, column, text),
                ),
            )

    def _load_users(self):
        with get_db_connection() as c:
            users = c.execute("SELECT id, username, is_admin FROM users ORDER BY id").fetchall()

        self.tbl_users.setRowCount(0)
        for uid, uname, adm in users:
            r = self.tbl_users.rowCount()
            self.tbl_users.insertRow(r)
            self.tbl_users.setItem(r, 0, QTableWidgetItem(str(uid)))
            self.tbl_users.setItem(r, 1, QTableWidgetItem(uname))
            self.tbl_users.setItem(r, 2, QTableWidgetItem("Ja" if adm else "Nein"))
            # Aktionen
            self.tbl_users.setCellWidget(
                r,
                3,
                self._action_widget(
                    functools.partial(self._edit_user, uid, uname, adm),
                    functools.partial(self._delete_user, uid, uname, adm),
                ),
            )
            # Passwort‑Reset‑Button mit Icon‑Fallbacks
            pw_btn = QPushButton()
            key_icon = QIcon.fromTheme("dialog-password")
            if key_icon.isNull():
                key_icon = self.style().standardIcon(QStyle.SP_DialogResetButton)
            if key_icon.isNull():
                pw_btn.setText("🔑")
            else:
                pw_btn.setIcon(key_icon)
            pw_btn.setFixedWidth(36)
            pw_btn.setIconSize(QSize(16, 16))
            pw_btn.clicked.connect(functools.partial(self._reset_password, uid, uname))
            self.tbl_users.setCellWidget(r, 4, pw_btn)

    # ------------------------------------------------------------------
    # Button‑Factory mit Icon‑Fallbacks
    # ------------------------------------------------------------------
    def _action_widget(self, edit_cb, del_cb):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        # Edit‑Button
        b_edit = QPushButton()
        edit_icon = QIcon.fromTheme("document-edit")
        if edit_icon.isNull():
            edit_icon = self.style().standardIcon(QStyle.SP_FileDialogDetailedView)
        if edit_icon.isNull():
            b_edit.setText("✎")
        else:
            b_edit.setIcon(edit_icon)

        # Delete‑Button
        b_del = QPushButton()
        del_icon = QIcon.fromTheme("edit-delete")
        if del_icon.isNull():
            del_icon = self.style().standardIcon(QStyle.SP_TrashIcon)
        if del_icon.isNull():
            b_del.setText("🗑")
        else:
            b_del.setIcon(del_icon)

        # Einheitliche Größe & DPI‑Skalierung
        for btn in (b_edit, b_del):
            btn.setFixedWidth(32)
            btn.setIconSize(QSize(16, 16))
        b_edit.clicked.connect(edit_cb)
        b_del.clicked.connect(del_cb)

        lay.addWidget(b_edit)
        lay.addWidget(b_del)
        return w

    # ------------------------------------------------------------------
    # Suggestion‑CRUD
    # ------------------------------------------------------------------
    def _edit_suggestion(self, column: str, old_text: str):
        new_text, ok = QInputDialog.getText(self, "Eintrag ändern", "Neuer Wert:", text=old_text)
        if ok and new_text.strip() and new_text != old_text:
            with get_db_connection() as c:
                c.execute(
                    f"UPDATE fix_suggestions SET {column}=? WHERE {column}=?",
                    (new_text.strip(), old_text),
                )
                c.commit()
            self._refresh_all()

    def _delete_suggestion(self, column: str, text: str):
        if (
            QMessageBox.question(
                self,
                "Löschen bestätigen",
                f"'{text}' wirklich löschen?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            with get_db_connection() as c:
                c.execute(f"DELETE FROM fix_suggestions WHERE {column}=?", (text,))
                c.commit()
            self._refresh_all()

    # ------------------------------------------------------------------
    # Benutzer‑CRUD
    # ------------------------------------------------------------------
    def _edit_user(self, uid: int, uname: str, adm_flag: int):
        new_name, ok = QInputDialog.getText(self, "Benutzer ändern", "Neuer Benutzername:", text=uname)
        if not ok or not new_name.strip():
            return

        chk = QCheckBox("Benutzer hat Admin‑Rechte")
        chk.setChecked(bool(adm_flag))
        box = QMessageBox(self)
        box.setWindowTitle("Admin‑Status")
        box.setCheckBox(chk)
        box.setText("Admin‑Status anpassen?")
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if box.exec() != QMessageBox.Ok:
            return
        new_admin = int(chk.isChecked())

        with get_db_connection() as c:
            cur = c.cursor()
            # Name doppelt?
            cur.execute(
                "SELECT 1 FROM users WHERE lower(username)=lower(?) AND id<>?",
                (new_name, uid),
            )
            if cur.fetchone():
                QMessageBox.warning(self, "Fehler", "Benutzername existiert bereits.")
                return
            # Letzten Admin schützen
            if not new_admin and adm_flag:
                cur.execute("SELECT COUNT(*) FROM users WHERE is_admin=1 AND id<>?", (uid,))
                if cur.fetchone()[0] == 0:
                    QMessageBox.warning(
                        self,
                        "Verboten",
                        "Mindestens ein Admin‑Konto muss erhalten bleiben.",
                    )
                    return
            cur.execute("UPDATE users SET username=?, is_admin=? WHERE id=?", (new_name.strip(), new_admin, uid))
            c.commit()
        self._refresh_all()

    def _delete_user(self, uid: int, uname: str, adm_flag: int):
        if (
            QMessageBox.question(
                self,
                "Benutzer löschen",
                f"Benutzer '{uname}' wirklich löschen?",
                QMessageBox.Yes | QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        with get_db_connection() as c:
            cur = c.cursor()
            if adm_flag:
                cur.execute("SELECT COUNT(*) FROM users WHERE is_admin=1 AND id<>?", (uid,))
                if cur.fetchone()[0] == 0:
                    QMessageBox.warning(self, "Verboten", "Der letzte Admin darf nicht gelöscht werden.")
                    return
            cur.execute("DELETE FROM users WHERE id=?", (uid,))
            c.commit()
        self._refresh_all()

    # ------------------------------------------------------------------
    # Passwort‑Reset
    # ------------------------------------------------------------------
    def _reset_password(self, uid: int, uname: str):
        pw1, ok1 = QInputDialog.getText(
            self, "Passwort setzen", f"Neues Passwort für '{uname}':", QLineEdit.Password
        )
        if not ok1 or not pw1:
            return
        pw2, ok2 = QInputDialog.getText(self, "Bestätigung", "Passwort wiederholen:", QLineEdit.Password)
        if not ok2 or pw1 != pw2:
            QMessageBox.warning(self, "Fehler", "Passwörter stimmen nicht überein.")
            return

        hash_pw = bcrypt.hashpw(pw1.encode(), bcrypt.gensalt()).decode()
        with get_db_connection() as c:
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_pw, uid))
            c.commit()
        QMessageBox.information(self, "Erfolg", f"Passwort für '{uname}' geändert.")


# ----------------------------------------------------------------------
# Direktstart
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # High‑DPI‑Pixmaps für scharfe Icons auf Retina / 4K
    QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    # Admin‑ID bei Bedarf anpassen
    AdminDashboard(user_id=1).exec()
