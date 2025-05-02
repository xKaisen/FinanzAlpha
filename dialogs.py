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

from db import get_db_connection
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
            "Passwort muss mindestens 8 Zeichen lang sein,\njo einen Groß- und Kleinbuchstaben,\neine Zahl und ein Sonderzeichen enthalten."
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
            QMessageBox.critical(self, "Fehler bei Registrierung", f"Name schon vorhanden oder DB-Fehler:\n{e}")
            return

        QMessageBox.information(self, "Erfolg", "Benutzer angelegt")
        self.accept()


class ManageFixBetrageDialog(BaseDialog):
    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        set_unified_font(self, 15)
        font = self.font()
        font.setStyleStrategy(QFont.PreferAntialias)
        self.setFont(font)
        self.user_id = user_id

        # Persistente Vorschlagstabelle
        self._with_connection(lambda cur: cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fix_suggestions (
                user_id INTEGER,
                description TEXT,
                usage TEXT,
                PRIMARY KEY(user_id, description, usage)
            )
            """
        ))

        self.setWindowTitle("Fix-Beträge verwalten")
        self.resize(1000, 600)
        self.setMinimumWidth(1000)

        main_layout = QVBoxLayout(self)

        # Fix-Einträge-Tabelle
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

        # Eingabeformular
        form_layout = QHBoxLayout()

        # Name / Firma
        self.beschreibung_input = QComboBox()
        self.beschreibung_input.setEditable(True)
        self.beschreibung_input.setFont(self.font())
        besch_le = self.beschreibung_input.lineEdit()
        besch_le.setPlaceholderText("Name / Firma")
        form_layout.addWidget(self.beschreibung_input, 3)

        # Verwendungszweck
        self.nutzung_input = QComboBox()
        self.nutzung_input.setEditable(True)
        self.nutzung_input.setFont(self.font())
        nutz_le = self.nutzung_input.lineEdit()
        nutz_le.setPlaceholderText("Verwendungszweck")
        form_layout.addWidget(self.nutzung_input, 3)

        # Betrag
        self.betrag_input = QLineEdit()
        self.betrag_input.setFont(self.font())
        self.betrag_input.setPlaceholderText("Betrag (€)")
        form_layout.addWidget(self.betrag_input, 2)

        # Dauer (M) – nur 1–24 Monate
        self.dauer_input = QComboBox()
        self.dauer_input.setEditable(True)
        self.dauer_input.setFont(self.font())
        dauer_le = self.dauer_input.lineEdit()
        dauer_le.setPlaceholderText("Dauer (M)")
        self.dauer_input.addItems([str(i) for i in range(1, 25)])
        self.dauer_input.setCurrentText("")
        form_layout.addWidget(self.dauer_input, 2)

        # Startdatum
        self.startdatum_input = QDateEdit()
        self.startdatum_input.setFont(self.font())
        self.startdatum_input.setDisplayFormat("dd.MM.yyyy")
        self.startdatum_input.setDate(date.today().replace(day=1))
        form_layout.addWidget(self.startdatum_input, 1)

        main_layout.addLayout(form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.edit_mode = False
        self.current_edit_id = None

        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_edit.setFont(self.font())
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        btn_layout.addWidget(self.btn_edit)

        btn_add = QPushButton("Hinzufügen")
        btn_add.setFont(self.font())
        btn_add.clicked.connect(self.add_fix)
        btn_layout.addWidget(btn_add)

        btn_del = QPushButton("Löschen")
        btn_del.setFont(self.font())
        btn_del.clicked.connect(self.delete_selected)
        btn_layout.addWidget(btn_del)

        btn_clear = QPushButton("Leeren")
        btn_clear.setFont(self.font())
        btn_clear.clicked.connect(self._reset_form)
        btn_layout.addWidget(btn_clear)

        btn_close = QPushButton("Schließen")
        btn_close.setFont(self.font())
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        main_layout.addLayout(btn_layout)

        # Initialisierung
        self.load_fixes()
        self.setup_autocomplete()
        self.load_suggestions()

    def setup_autocomplete(self):
        for field, getter in ((self.beschreibung_input, self.get_descriptions),
                               (self.nutzung_input, self.get_usages)):
            model = QStringListModel(getter())
            comp = QCompleter(model, self)
            comp.setCaseSensitivity(Qt.CaseInsensitive)
            comp.setFilterMode(Qt.MatchStartsWith)
            comp.setCompletionMode(QCompleter.PopupCompletion)
            field.setCompleter(comp)
            field.lineEdit().textEdited.connect(
                lambda t, f=field: f.showPopup() if len(t) >= 2 else None
            )

    def load_suggestions(self):
        self.beschreibung_input.clear()
        self.beschreibung_input.addItems([""] + self.get_descriptions())
        self.nutzung_input.clear()
        self.nutzung_input.addItems([""] + self.get_usages())

    def get_descriptions(self):
        return self._with_connection(lambda cur: [r[0] for r in cur.execute(
            "SELECT description FROM fix_suggestions WHERE user_id=? ORDER BY description", (self.user_id,)
        )])

    def get_usages(self):
        return self._with_connection(lambda cur: [r[0] for r in cur.execute(
            "SELECT usage FROM fix_suggestions WHERE user_id=? ORDER BY usage", (self.user_id,)
        )])

    def load_fixes(self):
        rows = self._with_connection(lambda cur: cur.execute(
            "SELECT id, description, usage, amount, duration, start_date FROM recurring_entries "
            "WHERE user_id=? ORDER BY start_date", (self.user_id,)
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
            rows = self.table.selectionModel().selectedRows()
            if len(rows) != 1:
                QMessageBox.warning(self, "Fehler", "Bitte wählen Sie genau einen Eintrag aus.")
                return
            row = rows[0].row()
            self.current_edit_id = int(self.table.item(row, 0).text())
            self.beschreibung_input.setCurrentText(self.table.item(row, 1).text())
            self.nutzung_input.setCurrentText(self.table.item(row, 2).text())
            amt = self.table.item(row, 3).text().replace(' €', '').replace('.', ',')
            self.betrag_input.setText(amt)
            self.dauer_input.setCurrentText(self.table.item(row, 4).text())
            txt = self.table.item(row, 5).text()
            try:
                dt_obj = datetime.strptime(txt, "%d.%m.%Y").date()
            except:
                dt_obj = date.today().replace(day=1)
            self.startdatum_input.setDate(dt_obj)
            self.edit_mode = True
            self.btn_edit.setText("Speichern")
        else:
            try:
                val = Decimal(self.betrag_input.text().replace(',', '.'))
            except:
                QMessageBox.warning(self, "Fehler", "Bitte gültigen Betrag eingeben.")
                return
            desc = self.beschreibung_input.currentText().strip()
            usage = self.nutzung_input.currentText().strip()
            dur_text = self.dauer_input.currentText()
            if not dur_text.isdigit() or not (1 <= int(dur_text) <= 24):
                QMessageBox.warning(self, "Fehler", "Dauer muss zwischen 1 und 24 Monaten liegen.")
                return
            dur = int(dur_text)
            start = self.startdatum_input.date().toPython().replace(day=1)
            if not desc or not usage:
                QMessageBox.warning(self, "Fehler", "Felder dürfen nicht leer sein.")
                return
            # Update recurring entry
            self._with_connection(lambda cur: cur.execute(
                "UPDATE recurring_entries SET description=?,usage=?,amount=?,duration=?,start_date=? WHERE id=? AND user_id=?",
                (desc, usage, float(val), dur, start, self.current_edit_id, self.user_id)
            ))
            # Synchronize existing transactions
            self._with_connection(lambda cur: cur.execute(
                "UPDATE transactions SET description=?,\"usage\"=?,amount=? WHERE recurring_id=? AND user_id=?",
                (desc, usage, float(val), self.current_edit_id, self.user_id)
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
        dur_text = self.dauer_input.currentText()
        if not dur_text.isdigit() or not (1 <= int(dur_text) <= 24):
            QMessageBox.warning(self, "Fehler", "Dauer muss zwischen 1 und 24 Monaten liegen.")
            return
        dur = int(dur_text)
        start = self.startdatum_input.date().toPython().replace(day=1)
        if not desc or not usage:
            QMessageBox.warning(self, "Fehler", "Felder dürfen nicht leer sein.")
            return
        self._with_connection(lambda cur: cur.execute(
            "INSERT INTO recurring_entries (user_id, description, usage, amount, duration, start_date) VALUES (?, ?, ?, ?, ?, ?)",
            (self.user_id, desc, usage, float(amt), dur, start)
        ))
        self._with_connection(lambda cur: cur.execute(
            "INSERT OR IGNORE INTO fix_suggestions (user_id, description, usage) VALUES (?, ?, ?)",
            (self.user_id, desc, usage)
        ))
        QMessageBox.information(self, "Erfolg", "Fix-Betrag hinzugefügt.")
        self._reset_form()
        self.load_fixes()
        self.load_suggestions()

    def delete_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Fehler", "Keine Auswahl.")
            return
        ids = [int(self.table.item(r.row(), 0).text()) for r in rows]
        if QMessageBox.question(
            self, "Löschen", f"Sollen {len(ids)} Einträge gelöscht werden?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No
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
