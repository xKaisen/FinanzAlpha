# ui/dialogs.py

import os
from datetime import date, datetime

import bcrypt
from decimal import Decimal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QDateEdit, QHeaderView, QComboBox, QCompleter
)
from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtGui import QFont

from core.db import get_db_connection
from utils import check_password, set_unified_font


class BaseDialog(QDialog):
    def _with_connection(self, fn, *args, **kwargs):
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            result = fn(cur, *args, **kwargs)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class RegistrationDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        set_unified_font(self, 13)
        self.setWindowTitle("Registrierung")
        self.resize(300, 200)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Benutzername:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("Passwort:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)

        hint = QLabel(
            "Passwort muss mindestens 8 Zeichen lang sein,\n"
            "je einen Groß- und Kleinbuchstaben,\n"
            "eine Zahl und ein Sonderzeichen enthalten."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11pt;")
        layout.addWidget(hint)

        self.register_btn = QPushButton("Registrieren")
        self.register_btn.clicked.connect(self.register)
        layout.addWidget(self.register_btn)

    def register(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text()
        if not user or not pwd:
            QMessageBox.warning(self, "Fehler", "Bitte alle Felder ausfüllen")
            return
        valid, msg = check_password(pwd)
        if not valid:
            QMessageBox.warning(self, "Fehler", msg)
            return
        pwd_hash = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            self._with_connection(lambda cur: cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (user, pwd_hash)
            ))
        except Exception as e:
            QMessageBox.critical(self, "Fehler bei Registrierung",
                                 f"Name schon vorhanden oder DB-Fehler:\n{e}")
            return

        QMessageBox.information(self, "Erfolg", "Benutzer angelegt")
        self.accept()


class ManageFixBetrageDialog(BaseDialog):
    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        set_unified_font(self, 15)
        font = self.font(); font.setStyleStrategy(QFont.PreferAntialias)
        self.setFont(font)
        self.user_id = user_id

        # ensure suggestion tables exist
        self._with_connection(lambda cur: cur.execute("""
            CREATE TABLE IF NOT EXISTS fix_suggestions (
                user_id INTEGER,
                description TEXT,
                usage TEXT,
                PRIMARY KEY(user_id, description, usage)
            )
        """))
        self._with_connection(lambda cur: cur.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                user_id INTEGER,
                suggestion_type TEXT,
                text TEXT,
                PRIMARY KEY(user_id, suggestion_type, text)
            )
        """))

        self.setWindowTitle("Fix-Beträge verwalten")
        self.resize(1000, 600)
        self.setMinimumWidth(1000)

        main_layout = QVBoxLayout(self)

        # recurring entries table
        self.table = QTableWidget(0, 6)
        self.table.setFont(self.font())
        self.table.setHorizontalHeaderLabels([
            "ID", "Name / Firma", "Verwendungszweck", "Betrag (€)", "Dauer (M)", "Startdatum"
        ])
        for col in range(1, 6):
            mode = QHeaderView.Stretch if col < 3 else QHeaderView.ResizeToContents
            self.table.horizontalHeader().setSectionResizeMode(col, mode)
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        main_layout.addWidget(self.table)

        # form inputs
        form_layout = QHBoxLayout()
        self.beschreibung_input = QComboBox(); self.beschreibung_input.setEditable(True)
        self.beschreibung_input.lineEdit().setPlaceholderText("Name / Firma")
        form_layout.addWidget(self.beschreibung_input, 3)

        self.nutzung_input = QComboBox(); self.nutzung_input.setEditable(True)
        self.nutzung_input.lineEdit().setPlaceholderText("Verwendungszweck")
        form_layout.addWidget(self.nutzung_input, 3)

        self.betrag_input = QLineEdit(); self.betrag_input.setPlaceholderText("Betrag (€)")
        form_layout.addWidget(self.betrag_input, 2)

        self.dauer_input = QComboBox(); self.dauer_input.setEditable(True)
        self.dauer_input.lineEdit().setPlaceholderText("Dauer (M)")
        self.dauer_input.addItems([str(i) for i in range(1, 25)])
        self.dauer_input.setCurrentText("")
        form_layout.addWidget(self.dauer_input, 2)

        self.startdatum_input = QDateEdit()
        self.startdatum_input.setDisplayFormat("dd.MM.yyyy")
        self.startdatum_input.setDate(date.today().replace(day=1))
        form_layout.addWidget(self.startdatum_input, 1)

        main_layout.addLayout(form_layout)

        # buttons
        btn_layout = QHBoxLayout()
        self.edit_mode = False
        self.current_edit_id = None

        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        btn_layout.addWidget(self.btn_edit)

        btn_add = QPushButton("Hinzufügen"); btn_add.clicked.connect(self.add_fix)
        btn_layout.addWidget(btn_add)

        btn_del = QPushButton("Löschen"); btn_del.clicked.connect(self.delete_selected)
        btn_layout.addWidget(btn_del)

        btn_clear = QPushButton("Leeren"); btn_clear.clicked.connect(self._reset_form)
        btn_layout.addWidget(btn_clear)

        btn_close = QPushButton("Schließen"); btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        main_layout.addLayout(btn_layout)

        # initial load
        self.load_fixes()
        self.setup_autocomplete()
        self.load_suggestions()

    def setup_autocomplete(self):
        def setup_combo(combo: QComboBox, items: list[str]):
            combo.clear()
            combo.addItems(items)
            completer = QCompleter(combo.model(), self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            combo.setCompleter(completer)

        setup_combo(self.beschreibung_input, self.get_descriptions())
        setup_combo(self.nutzung_input, self.get_usages())
    def load_suggestions(self):
        self.beschreibung_input.clear()
        self.beschreibung_input.addItems([""] + self.get_descriptions())
        self.nutzung_input.clear()
        self.nutzung_input.addItems([""] + self.get_usages())

    def get_descriptions(self):
        return self._with_connection(lambda cur: [
            r[0] for r in cur.execute(
                "SELECT description FROM fix_suggestions WHERE user_id=? ORDER BY description",
                (self.user_id,)
            ).fetchall()
        ])

    def get_usages(self):
        return self._with_connection(lambda cur: [
            r[0] for r in cur.execute(
                "SELECT usage FROM fix_suggestions WHERE user_id=? ORDER BY usage",
                (self.user_id,)
            ).fetchall()
        ])

    def load_fixes(self):
        rows = self._with_connection(lambda cur: cur.execute(
            "SELECT id, description, usage, amount, duration, start_date "
            "FROM recurring_entries WHERE user_id=? ORDER BY start_date",
            (self.user_id,)
        ).fetchall())
        self.table.setRowCount(0)
        for eid, desc, usage, amt, dur, start in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(eid)))
            self.table.setItem(r, 1, QTableWidgetItem(desc))
            self.table.setItem(r, 2, QTableWidgetItem(usage))
            self.table.setItem(r, 3, QTableWidgetItem(f"{Decimal(str(amt)):.2f} €"))
            self.table.setItem(r, 4, QTableWidgetItem(str(dur)))
            sd = start.strftime("%d.%m.%Y") if hasattr(start, 'strftime') else str(start)
            self.table.setItem(r, 5, QTableWidgetItem(sd))

    def on_edit_clicked(self):
        if not self.edit_mode:
            sel = self.table.selectionModel().selectedRows()
            if len(sel) != 1:
                QMessageBox.warning(self, "Fehler", "Bitte wählen Sie genau einen Eintrag aus.")
                return
            row = sel[0].row()
            self.current_edit_id = int(self.table.item(row, 0).text())
            self.beschreibung_input.setCurrentText(self.table.item(row, 1).text())
            self.nutzung_input.setCurrentText(self.table.item(row, 2).text())
            amt = self.table.item(row, 3).text().replace(' €', '').replace('.', ',')
            self.betrag_input.setText(amt)
            self.dauer_input.setCurrentText(self.table.item(row, 4).text())
            try:
                dt = datetime.strptime(self.table.item(row, 5).text(), "%d.%m.%Y").date()
            except:
                dt = date.today().replace(day=1)
            self.startdatum_input.setDate(dt)
            self.edit_mode = True
            self.btn_edit.setText("Speichern")
        else:
            # save edited fix entry and suggestions
            try:
                val = Decimal(self.betrag_input.text().replace(',', '.'))
            except:
                QMessageBox.warning(self, "Fehler", "Bitte gültigen Betrag eingeben.")
                return
            desc = self.beschreibung_input.currentText().strip()
            usage = self.nutzung_input.currentText().strip()
            dur_txt = self.dauer_input.currentText()
            if not dur_txt.isdigit() or not (1 <= int(dur_txt) <= 24):
                QMessageBox.warning(self, "Fehler", "Dauer zwischen 1 und 24 Monaten.")
                return
            dur = int(dur_txt)
            start = self.startdatum_input.date().toPython().replace(day=1)
            if not desc or not usage:
                QMessageBox.warning(self, "Fehler", "Felder dürfen nicht leer sein.")
                return

            self._with_connection(lambda cur: cur.execute(
                "UPDATE recurring_entries SET description=?,usage=?,amount=?,duration=?,start_date=? "
                "WHERE id=? AND user_id=?",
                (desc, usage, float(val), dur, start, self.current_edit_id, self.user_id)
            ))
            self._with_connection(lambda cur: cur.execute(
                "UPDATE transactions SET description=?,\"usage\"=?,amount=? "
                "WHERE recurring_id=? AND user_id=?",
                (desc, usage, float(val), self.current_edit_id, self.user_id)
            ))
            # also save into general suggestions
            self._with_connection(lambda cur: cur.execute(
                "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
                (self.user_id, "description", desc)
            ))
            self._with_connection(lambda cur: cur.execute(
                "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
                (self.user_id, "usage", usage)
            ))

            QMessageBox.information(self, "Erfolg", "Eintrag gespeichert.")
            self.edit_mode = False
            self.btn_edit.setText("Bearbeiten")
            self._reset_form()
            self.load_fixes()
            self.load_suggestions()

    def add_fix(self):
        desc = self.beschreibung_input.currentText().strip()
        usage = self.nutzung_input.currentText().strip()
        try:
            amt = Decimal(self.betrag_input.text().replace(',', '.'))
        except:
            QMessageBox.warning(self, "Fehler", "Bitte gültigen Betrag eingeben.")
            return
        dur_txt = self.dauer_input.currentText()
        if not dur_txt.isdigit() or not (1 <= int(dur_txt) <= 24):
            QMessageBox.warning(self, "Fehler", "Dauer zwischen 1 und 24 Monaten.")
            return
        dur = int(dur_txt)
        start = self.startdatum_input.date().toPython().replace(day=1)
        if not desc or not usage:
            QMessageBox.warning(self, "Fehler", "Felder dürfen nicht leer sein.")
            return

        self._with_connection(lambda cur: cur.execute(
            "INSERT INTO recurring_entries (user_id, description, usage, amount, duration, start_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (self.user_id, desc, usage, float(amt), dur, start)
        ))
        # record fix suggestion and general suggestions
        self._with_connection(lambda cur: cur.execute(
            "INSERT OR IGNORE INTO fix_suggestions (user_id, description, usage) VALUES (?, ?, ?)",
            (self.user_id, desc, usage)
        ))
        self._with_connection(lambda cur: cur.execute(
            "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
            (self.user_id, "description", desc)
        ))
        self._with_connection(lambda cur: cur.execute(
            "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
            (self.user_id, "usage", usage)
        ))

        QMessageBox.information(self, "Erfolg", "Fix-Betrag hinzugefügt.")
        self._reset_form()
        self.load_fixes()
        self.load_suggestions()

    def delete_selected(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Keine Auswahl", "Bitte wählen Sie mindestens einen Eintrag.")
            return
        ids = [int(self.table.item(r.row(), 0).text()) for r in sel]
        if QMessageBox.question(
            self, "Löschen bestätigen",
            f"Sollen wirklich {len(ids)} Einträge gelöscht werden?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._with_connection(lambda cur: cur.executemany(
            "DELETE FROM recurring_entries WHERE id=? AND user_id=?",
            [(i, self.user_id) for i in ids]
        ))
        self._with_connection(lambda cur: cur.executemany(
            "DELETE FROM transactions WHERE recurring_id=? AND user_id=?",
            [(i, self.user_id) for i in ids]
        ))
        self.load_fixes()
        self.load_suggestions()

    def _reset_form(self):
        self.beschreibung_input.clearEditText()
        self.nutzung_input.clearEditText()
        self.betrag_input.clear()
        self.dauer_input.setCurrentText("")
        self.startdatum_input.setDate(date.today().replace(day=1))


class ManageSuggestionsDialog(BaseDialog):
    """Dialog, um Vorschläge zu Name/Firma und Verwendungszweck zu verwalten."""

    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.user_id = user_id

        self.setWindowTitle("Verwaltung")
        self.resize(1000, 600)
        self.setMinimumWidth(1000)

        self.display_to_internal = {
            "Name/Firma": "description",
            "Verwendungszweck": "usage"
        }
        self.internal_to_display = {v: k for k, v in self.display_to_internal.items()}

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Kategorie", "Vorschlag"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        form = QHBoxLayout()
        self.type_cb = QComboBox(); self.type_cb.addItems(list(self.display_to_internal.keys()))
        form.addWidget(QLabel("Kategorie:")); form.addWidget(self.type_cb)

        self.text_le = QLineEdit(); self.text_le.setPlaceholderText("Neuen Vorschlag eingeben…")
        form.addWidget(self.text_le)

        add_btn = QPushButton("Hinzufügen"); add_btn.clicked.connect(self.add_suggestion)
        form.addWidget(add_btn)
        layout.addLayout(form)

        del_btn = QPushButton("Löschen"); del_btn.clicked.connect(self.delete_selected)
        layout.addWidget(del_btn, alignment=Qt.AlignRight)

        close_btn = QPushButton("Schließen"); close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        self._load_table()

    def _load_table(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT suggestion_type, text FROM suggestions "
            "WHERE user_id = ? ORDER BY suggestion_type, text",
            (self.user_id,)
        )
        rows = cur.fetchall()
        conn.close()

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for typ_int, txt in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(self.internal_to_display[typ_int]))
            item = QTableWidgetItem(txt)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.table.setItem(r, 1, item)
        self.table.blockSignals(False)

    def add_suggestion(self):
        disp = self.type_cb.currentText()
        txt = self.text_le.text().strip()
        if not txt:
            QMessageBox.warning(self, "Fehler", "Bitte einen Vorschlag eingeben.")
            return
        internal = self.display_to_internal[disp]
        self._with_connection(lambda cur: cur.execute(
            "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?, ?, ?)",
            (self.user_id, internal, txt)
        ))
        self.text_le.clear()
        self._load_table()

    def delete_selected(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Keine Auswahl", "Bitte wählen Sie mindestens einen Vorschlag.")
            return
        count = len(sel)
        if QMessageBox.question(
            self, "Löschen bestätigen",
            f"Sollen wirklich {count} Vorschlag(e) gelöscht werden?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        to_del = []
        for idx in sel:
            disp = self.table.item(idx.row(), 0).text()
            txt = self.table.item(idx.row(), 1).text()
            to_del.append((self.user_id, self.display_to_internal[disp], txt))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.executemany(
            "DELETE FROM suggestions WHERE user_id = ? AND suggestion_type = ? AND text = ?",
            to_del
        )
        conn.commit()
        conn.close()

        self._load_table()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 1:
            return
        disp = self.table.item(item.row(), 0).text()
        internal = self.display_to_internal[disp]
        texts = [
            self.table.item(r, 1).text().strip()
            for r in range(self.table.rowCount())
            if self.table.item(r, 0).text() == disp
        ]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM suggestions WHERE user_id = ? AND suggestion_type = ?",
            (self.user_id, internal)
        )
        for t in texts:
            if t:
                cur.execute(
                    "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?, ?, ?)",
                    (self.user_id, internal, t)
                )
        conn.commit()
        conn.close()
