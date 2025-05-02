import os
from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QColor, QFont

from db import get_db_connection
from constants import MONTHS
from dialogs import ManageFixBetrageDialog

class Dashboard(QMainWindow):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

        # Einheitliche Basis-Schrift auf 15 pt
        base_font = QFont()
        base_font.setPointSize(15)
        QApplication.instance().setFont(base_font)

        # Fenster & Settings
        self.settings_file = os.path.join(os.path.expanduser("~"), ".finanzapp_settings.ini")
        self.settings = QSettings(self.settings_file, QSettings.IniFormat)
        self.setWindowTitle("FinanzApp Alpha 0.1.1")
        self.setMinimumSize(800, 600)
        self.restoreGeometry(self.settings.value("geometry", self.saveGeometry()))
        self.restoreState(self.settings.value("windowState", self.saveState()))

        # Haupt-Layout
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # Obere Leiste
        top = QHBoxLayout()
        self.logout_btn = QPushButton("Abmelden")
        self.logout_btn.setFont(base_font)
        self.logout_btn.clicked.connect(self.logout)
        top.addWidget(self.logout_btn)

        # Suchfeld
        self.search_input = QLineEdit()
        self.search_input.setFont(base_font)
        self.search_input.setPlaceholderText("Suche Name/Firma oder Verwendungszweck...")
        self.search_input.setFixedWidth(500)  # Breiteres Suchfeld, jetzt 500px
        self.search_input.textChanged.connect(self.filter_table)
        top.addWidget(self.search_input)

        top.addStretch()

        lbl_year = QLabel("Jahr:")
        lbl_year.setFont(base_font)
        top.addWidget(lbl_year)
        self.year_cb = QComboBox()
        self.year_cb.setFont(base_font)
        years = ["Archiv 2020-2024"] + [str(y) for y in range(date.today().year-1, date.today().year+5)]
        self.year_cb.addItems(years)
        self.year_cb.setCurrentText(str(date.today().year))
        self.year_cb.currentIndexChanged.connect(self.trigger_data_load)
        top.addWidget(self.year_cb)

        lbl_month = QLabel("Monat:")
        lbl_month.setFont(base_font)
        top.addWidget(lbl_month)
        self.month_cb = QComboBox()
        self.month_cb.setFont(base_font)
        self.month_cb.addItems(["Alle"] + MONTHS)
        self.month_cb.setCurrentIndex(date.today().month)
        self.month_cb.currentIndexChanged.connect(self.trigger_data_load)
        top.addWidget(self.month_cb)

        fix_btn = QPushButton("Fixkosten")
        fix_btn.setFont(base_font)
        fix_btn.clicked.connect(self.open_manage_fix_betrage)
        top.addWidget(fix_btn)

        self.main_layout.addLayout(top)

        # Transaktionstabelle
        self.table = QTableWidget(0, 7)
        self.table.setSortingEnabled(True)
        self.table.setFont(base_font)
        self.table.setHorizontalHeaderLabels([
            "Datum", "Beschreibung", "Verwendungszweck", "Betrag", "Bezahlt", "ID", "FixID"
        ])
        self.table.setColumnHidden(5, True)
        self.table.setColumnHidden(6, True)

        hdr = self.table.horizontalHeader()
        hdr.setFont(base_font)
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 120)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(False)
        hdr.setDefaultAlignment(Qt.AlignCenter | Qt.TextWordWrap)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellClicked.connect(self.handle_cell_click)
        self.main_layout.addWidget(self.table)

        # Saldo & Offen
        summary = QHBoxLayout()
        self.balance_lbl = QLabel("Saldo: 0,00 €")
        self.open_lbl = QLabel("Offen: 0,00 €")
        special_font = QFont()
        special_font.setPointSize(18)
        special_font.setBold(True)
        self.balance_lbl.setFont(special_font)
        self.open_lbl.setFont(special_font)
        summary.addWidget(self.balance_lbl)
        summary.addStretch()
        summary.addWidget(self.open_lbl)
        self.main_layout.addLayout(summary)

        # Eingabe + Buttons
        inp = QHBoxLayout()
        self.desc_input = QComboBox()
        self.desc_input.setEditable(True)
        self.desc_input.setFont(base_font)
        desc_le = self.desc_input.lineEdit()
        desc_le.setPlaceholderText("Name / Firma")
        desc_le.setStyleSheet("QLineEdit { color: white; } QLineEdit:placeholder { color: gray; }")
        self.desc_input.setFixedWidth(300)
        inp.addWidget(self.desc_input)

        self.usage_input = QComboBox()
        self.usage_input.setEditable(True)
        self.usage_input.setFont(base_font)
        usage_le = self.usage_input.lineEdit()
        usage_le.setPlaceholderText("Verwendungszweck")
        usage_le.setStyleSheet("QLineEdit { color: white; } QLineEdit:placeholder { color: gray; }")
        self.usage_input.setFixedWidth(300)
        inp.addWidget(self.usage_input)

        self.amount_input = QLineEdit()
        self.amount_input.setFont(base_font)
        self.amount_input.setPlaceholderText("Betrag (€)")
        self.amount_input.setStyleSheet("QLineEdit { color: white; } QLineEdit:placeholder { color: gray; }")
        self.amount_input.setFixedWidth(150)
        self.amount_input.returnPressed.connect(self.add_transaction)
        inp.addWidget(self.amount_input)

        add_btn = QPushButton("Hinzufügen")
        add_btn.setFont(base_font)
        add_btn.setFixedWidth(150)
        add_btn.clicked.connect(self.add_transaction)
        inp.addWidget(add_btn)

        del_btn = QPushButton("Löschen")
        del_btn.setFont(base_font)
        del_btn.setFixedWidth(150)
        del_btn.clicked.connect(self.delete_selected_transaction)
        inp.addWidget(del_btn)

        self.main_layout.addLayout(inp)

        # Timer für verzögertes Laden
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.load_data)

        # Init
        self.insert_missing_fix_transactions()
        self.load_description_suggestions()
        self.load_usage_suggestions_for_input()
        self.trigger_data_load()

        self.desc_input.setCurrentText("")
        self.usage_input.setCurrentText("")

    def trigger_data_load(self):
        self._timer.start(150)

    def load_data(self):
        self.table.setSortingEnabled(False)
        year = self.year_cb.currentText()
        month = self.month_cb.currentIndex()
        params, cond = [self.user_id], ["user_id = ?"]
        if year.startswith("Archiv"):
            cond.append("strftime('%Y',date) BETWEEN '2020' AND '2024'")
        else:
            cond.append("strftime('%Y',date)=?")
            params.append(year)
            if month > 0:
                cond.append("strftime('%m',date)=?")
                params.append(f"{month:02d}")
        sql = (
            "SELECT id,date,description,\"usage\",amount,paid,recurring_id "
            "FROM transactions WHERE " + " AND ".join(cond) + " ORDER BY date DESC"
        )
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        self.table.setRowCount(0)
        bal = Decimal('0.0')
        open_sum = Decimal('0.0')
        for tid, dts_iso, desc, usage, amt, paid, recid in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            bal += Decimal(str(amt))
            yyyy, mm, dd = dts_iso.split('-')
            item_date = QTableWidgetItem(f"{dd}.{mm}")
            item_date.setData(Qt.UserRole, dts_iso)
            self.table.setItem(r, 0, item_date)
            self.table.setItem(r, 1, QTableWidgetItem(desc or ""))
            self.table.setItem(r, 2, QTableWidgetItem(usage or ""))
            amt_item = QTableWidgetItem(f"{Decimal(str(amt)):.2f} €")
            amt_item.setForeground(QColor("#32CD32") if amt >= 0 else QColor("#FF0000"))
            self.table.setItem(r, 3, amt_item)
            symbol = ""
            if recid and amt < 0:
                symbol = "✓" if paid else "✗"
                if not paid:
                    open_sum += Decimal(str(amt))
            self.table.setItem(r, 4, QTableWidgetItem(symbol))
            self.table.setItem(r, 5, QTableWidgetItem(str(tid)))
            self.table.setItem(r, 6, QTableWidgetItem(str(recid or "")))
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.AscendingOrder)
        self.balance_lbl.setText(
            f"Saldo: {bal:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        self.open_lbl.setText(
            f"Offen: {open_sum:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        self.balance_lbl.setStyleSheet("color: #32CD32;" if bal >= 0 else "color: #FF0000;")
        self.open_lbl.setStyleSheet("color: white;" if open_sum == 0 else "color: #FF0000;")
        # Filter neu anwenden, damit neue Einträge entsprechend versteckt werden
        self.filter_table(self.search_input.text())

    def add_transaction(self):
        desc = self.desc_input.currentText().strip()
        usage = self.usage_input.currentText().strip()
        try:
            amt = Decimal(self.amount_input.text().replace(',', '.'))
        except Exception:
            QMessageBox.warning(self, "Ungültig", "Bitte gültigen Betrag eingeben.")
            return
        dts = date.today().isoformat()
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transactions(user_id,date,description,\"usage\",amount,paid) VALUES(?,?,?,?,?,1)",
            (self.user_id, dts, desc, usage, float(amt))
        )
        conn.commit()
        conn.close()
        # Suche zurücksetzen, damit neue Einträge sichtbar werden
        self.search_input.clear()
        self.desc_input.setCurrentText("")
        self.usage_input.setCurrentText("")
        self.amount_input.clear()
        self.insert_missing_fix_transactions()
        self.trigger_data_load()

    def delete_selected_transaction(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Keine Auswahl", "Bitte wählen Sie mindestens eine Transaktion.")
            return
        ids = [int(self.table.item(i.row(), 5).text()) for i in selected]
        if QMessageBox.question(
            self, "Löschen bestätigen",
            f"Sollen wirklich {len(ids)} Transaktion(en) gelöscht werden?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        conn = self.get_db()
        cur = conn.cursor()
        cur.executemany(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            [(tid, self.user_id) for tid in ids]
        )
        conn.commit()
        conn.close()
        self.trigger_data_load()

    def handle_cell_click(self, row, col):
        if col == 4:
            recid = int(self.table.item(row, 6).text() or 0)
            amt_text = self.table.item(row, 3).text().replace(" €", "").replace(".", "").replace(",", ".")
            amt = Decimal(amt_text)
            if recid and amt < 0:
                tid = int(self.table.item(row, 5).text())
                paid = self.table.item(row, 4).text() == "✓"
                conn = self.get_db()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE transactions SET paid=? WHERE id=? AND user_id= ?",
                    (0 if paid else 1, tid, self.user_id)
                )
                conn.commit()
                conn.close()
                self.trigger_data_load()

    def insert_missing_fix_transactions(self):
        today = date.today()
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, description, \"usage\", amount, duration, start_date FROM recurring_entries WHERE user_id=?",
            (self.user_id,)
        )
        recs = cur.fetchall()
        cur.execute(
            "SELECT recurring_id, strftime('%Y', date), strftime('%m', date)"
            " FROM transactions WHERE user_id=? AND recurring_id IS NOT NULL",
            (self.user_id,)
        )
        existing = {(r[0], int(r[1]), int(r[2])) for r in cur.fetchall()}

        inserts, params = [], []
        for rec_id, desc, usage, amt, dur, start in recs:
            dur = min(dur, 24)
            year, month, _ = map(int, start.split('-'))
            current = date(year, month, 1)
            end_date = date(year + (month + dur - 2) // 12, ((month + dur - 2) % 12) + 1, 1)
            while current <= end_date:
                key = (rec_id, current.year, current.month)
                if key not in existing:
                    inserts.append("(?, ?, ?, ?, ?, 0, ?)")
                    params.extend([self.user_id, current.isoformat(), desc, usage, float(amt), rec_id])
                    existing.add(key)
                next_month = current.month % 12 + 1
                next_year = current.year + (current.month // 12)
                current = date(next_year, next_month, 1)
        if inserts:
            sql_insert = (
                "INSERT INTO transactions(user_id,date,description,\"usage\",amount,paid,recurring_id) VALUES "
                + ",".join(inserts)
            )
            cur.execute(sql_insert, params)
            conn.commit()
        conn.close()

    def open_manage_fix_betrage(self):
        dlg = ManageFixBetrageDialog(self.user_id, self)
        dlg.exec()
        self.insert_missing_fix_transactions()
        self.trigger_data_load()

    def load_description_suggestions(self):
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT description FROM transactions "
            "WHERE user_id=? ORDER BY description LIMIT 50",
            (self.user_id,)
        )
        items = [row[0] for row in cur.fetchall() if row[0]]
        conn.close()
        self.desc_input.clear()
        self.desc_input.addItems(items)

    def load_usage_suggestions_for_input(self):
        desc = self.desc_input.currentText().strip()
        conn = self.get_db()
        cur = conn.cursor()
        if desc:
            cur.execute(
                "SELECT DISTINCT \"usage\" FROM transactions "
                "WHERE user_id=? AND description=? LIMIT 50",
                (self.user_id, desc)
            )
        else:
            cur.execute(
                "SELECT DISTINCT \"usage\" FROM transactions "
                "WHERE user_id=? LIMIT 50",
                (self.user_id,)
            )
        items = [row[0] for row in cur.fetchall() if row[0]]
        conn.close()
        self.usage_input.clear()
        self.usage_input.addItems(items)

    def logout(self):
        from login import LoginWindow
        self.close()
        win = LoginWindow()
        win.show()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def get_db(self):
        return get_db_connection()

    def filter_table(self, text):
        """Filtert die Tabelle nach Suchbegriff in Beschreibung oder Verwendungszweck und hebt Treffer hervor."""
        text = text.lower()
        highlight_brush = QColor(128, 0, 128, 100)  # sanftes Lila mit Transparenz  # Helles Gelb
        for row in range(self.table.rowCount()):
            desc_item = self.table.item(row, 1)
            usage_item = self.table.item(row, 2)
            desc = desc_item.text().lower()
            usage = usage_item.text().lower()
            match = text in desc or text in usage
            # Zeile zeigen/verstecken
            self.table.setRowHidden(row, not match)
            # Hintergrund auf Standard (Theme) zurücksetzen
            desc_item.setBackground(Qt.NoBrush)
            usage_item.setBackground(Qt.NoBrush)
            # Hervorhebung
            if text:
                if text in desc:
                    desc_item.setBackground(highlight_brush)
                if text in usage:
                    usage_item.setBackground(highlight_brush)
