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

from core.db import get_db_connection
from utils import set_unified_font


class AdminDashboard(QDialog):
    """Admin-Dashboard für Benutzer-, Vorschlags- und Passwortverwaltung."""

    def __init__(self, user_id: int, parent=None):
        super().__init__(parent)
        set_unified_font(self, 14)
        self.setWindowTitle("Admin-Dashboard")
        self.resize(900, 640)

        # Admin-Prüfung
        if not self._is_admin(user_id):
            QMessageBox.critical(self, "Zugriff verweigert", "Du besitzt keine Admin-Rechte.")
            self.close()
            return

        main = QVBoxLayout(self)

        # Logout-Button oben
        top = QHBoxLayout()
        top.addStretch()
        btn_logout = QPushButton("Abmelden")
        btn_logout.clicked.connect(self._logout)
        top.addWidget(btn_logout)
        main.addLayout(top)

        # Tabs
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        # Tabellen für Vorschläge und Benutzer
        self.tbl_desc = self._create_table(["Text", "Aktion"], stretch_col=0)
        self.tbl_usage = self._create_table(["Text", "Aktion"], stretch_col=0)
        self.tbl_users = self._create_table([
            "ID", "Benutzername", "Admin", "Aktion", "PW ändern"
        ], stretch_col=1)

        self.tabs.addTab(self.tbl_desc, "Name / Firma")
        self.tabs.addTab(self.tbl_usage, "Verwendungszweck")
        self.tabs.addTab(self.tbl_users, "Benutzer")

        self._refresh_all()

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
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT is_admin FROM users WHERE id=?", (uid,))
            row = cur.fetchone()
        return bool(row and row[0])

    def _refresh_all(self):
        self._load_suggestions(self.tbl_desc, "description")
        self._load_suggestions(self.tbl_usage, "usage")
        self._load_users()

    def _load_suggestions(self, tbl: QTableWidget, column: str):
        with get_db_connection() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT {column} FROM fix_suggestions ORDER BY {column}"
            ).fetchall()
        tbl.setRowCount(0)
        for (text,) in rows:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem(text))
            tbl.setCellWidget(r, 1, self._action_widget(
                functools.partial(self._edit_suggestion, column, text),
                functools.partial(self._delete_suggestion, column, text)
            ))

    def _load_users(self):
        with get_db_connection() as conn:
            users = conn.execute(
                "SELECT id, username, is_admin FROM users ORDER BY id"
            ).fetchall()
        self.tbl_users.setRowCount(0)
        for uid, uname, adm in users:
            r = self.tbl_users.rowCount()
            self.tbl_users.insertRow(r)
            self.tbl_users.setItem(r, 0, QTableWidgetItem(str(uid)))
            self.tbl_users.setItem(r, 1, QTableWidgetItem(uname))
            self.tbl_users.setItem(r, 2, QTableWidgetItem("Ja" if adm else "Nein"))
            self.tbl_users.setCellWidget(r, 3, self._action_widget(
                functools.partial(self._edit_user, uid, uname, adm),
                functools.partial(self._delete_user, uid, uname, adm)
            ))
            pw_btn = QPushButton("Passwort")
            pw_btn.setToolTip("Passwort neu setzen")
            pw_btn.setFixedWidth(90)
            pw_btn.clicked.connect(functools.partial(self._change_password_dialog, uid, uname))
            self.tbl_users.setCellWidget(r, 4, pw_btn)

    def _action_widget(self, edit_cb, del_cb):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        b_edit = QPushButton("Bearbeiten")
        b_del = QPushButton("Löschen")
        for btn in (b_edit, b_del):
            btn.setFixedWidth(80)
        b_edit.clicked.connect(edit_cb)
        b_del.clicked.connect(del_cb)
        lay.addWidget(b_edit)
        lay.addWidget(b_del)
        return w

    def _edit_suggestion(self, column: str, old_text: str):
        new_text, ok = QInputDialog.getText(self, "Vorschlag bearbeiten", f"Neuer Wert für {column}:", text=old_text)
        if ok and new_text and new_text.strip() != old_text:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE fix_suggestions SET {column} = ? WHERE {column} = ?",
                    (new_text.strip(), old_text)
                )
                conn.commit()
            self._refresh_all()

    def _delete_suggestion(self, column: str, text: str):
        if QMessageBox.question(self, "Löschen", f"Soll '{text}' aus Vorschlägen gelöscht werden?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"DELETE FROM fix_suggestions WHERE {column} = ?", (text,))
                conn.commit()
            self._refresh_all()

    def _edit_user(self, uid: int, uname: str, adm: bool):
        new_is_admin = QMessageBox.question(
            self, "Adminrechte ändern",
            f"Soll {uname} {'kein Admin mehr sein' if adm else 'zum Admin gemacht werden'}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes

        if new_is_admin != adm:
            with get_db_connection() as conn:
                conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(new_is_admin), uid))
                conn.commit()
            self._refresh_all()

    def _delete_user(self, uid: int, uname: str, adm: bool):
        if adm:
            QMessageBox.warning(self, "Nicht erlaubt", "Admins können nicht gelöscht werden.")
            return

        if QMessageBox.question(self, "Benutzer löschen",
                                f"Benutzer '{uname}' wirklich löschen?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = ?", (uid,))
                conn.commit()
            self._refresh_all()

    def _change_password_dialog(self, uid: int, uname: str):
        pw, ok = QInputDialog.getText(self, "Passwort neu setzen", f"Neues Passwort für '{uname}':", QLineEdit.Password)
        if ok and pw:
            if len(pw) < 8:
                QMessageBox.warning(self, "Fehler", "Passwort muss mindestens 8 Zeichen lang sein.")
                return
            hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
            with get_db_connection() as conn:
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, uid))
                conn.commit()
            QMessageBox.information(self, "Erfolg", f"Passwort für '{uname}' wurde neu gesetzt.")

    def _logout(self):
        self.close()
        try:
            self.parent().show()
        except Exception:
            pass


if __name__ == "__main__":
    QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    AdminDashboard(user_id=1).exec()
