import os
from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QMessageBox, QAbstractItemView, QSizePolicy,
    QCompleter
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QDate, QEvent
from PySide6.QtGui import QColor, QFont, QPalette

from core.db import get_db_connection
from constants import MONTHS
from ui.dialogs import ManageFixBetrageDialog
from core.version import __version__


class LoadDataThread(QThread):
    dataLoaded = Signal(list)

    def __init__(self, user_id, year, month):
        super().__init__()
        self.user_id = user_id
        self.year = year
        self.month = month

    def run(self):
        conn = get_db_connection()
        cur = conn.cursor()
        params = [self.user_id]
        cond = ["user_id = ?"]

        if self.year.startswith("Archiv"):
            cond.append("strftime('%Y',date) BETWEEN '2020' AND '2024'")
        else:
            cond.append("strftime('%Y', date) = ?")
            params.append(self.year)
            if self.month > 0:
                cond.append("strftime('%m', date) = ?")
                params.append(f"{self.month:02d}")

        sql = f"""
            SELECT id, date, description, "usage", amount, paid, recurring_id
            FROM transactions
            WHERE {' AND '.join(cond)}
            ORDER BY date ASC
        """
        rows = cur.execute(sql, params).fetchall()
        conn.close()
        self.dataLoaded.emit(rows)


class Dashboard(QDialog):
    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        # include minimize and maximize buttons
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        self.user_id = user_id
        self.login_window = None
        self.is_dark_mode = self.check_dark_mode()

        # suggestions persistence
        self._ensure_suggestions_table()
        self._seed_suggestions_from_existing_transactions()

        base_font = QFont()
        base_font.setPointSize(15)
        QApplication.instance().setFont(base_font)

        self.setWindowTitle(f"FinanzApp Alpha {__version__}")
        self.setMinimumSize(800, 600)

        central = QWidget()
        self.main_layout = QVBoxLayout(central)
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # build UI
        self.build_top_ui(base_font)
        self.build_table(base_font)
        self.build_summary_ui()
        self.build_input_ui(base_font)

        # footer
        text_color = "#FFFFFF" if self.is_dark_mode else "#000000"
        footer_layout = QHBoxLayout()
        version_label = QLabel(f"Version {__version__}")
        version_label.setAlignment(Qt.AlignLeft)
        version_label.setStyleSheet(f"color: {text_color}; font-size: 14pt; font-weight: bold;")
        footer_layout.addWidget(version_label)
        footer_layout.addStretch()
        copyright_label = QLabel("© 2025 xKAISEN. Alle Rechte vorbehalten.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet(f"color: {text_color}; font-size: 14pt; font-weight: bold;")
        footer_layout.addWidget(copyright_label)
        self.main_layout.addLayout(footer_layout)

        # timer for async load
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.trigger_data_load)

        # initial data load
        self.trigger_data_load()

    def _ensure_suggestions_table(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                user_id INTEGER,
                suggestion_type TEXT,
                text TEXT,
                PRIMARY KEY(user_id, suggestion_type, text)
            )
        """)
        conn.commit()
        conn.close()

    def _seed_suggestions_from_existing_transactions(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT description FROM transactions WHERE user_id = ?", (self.user_id,))
        for (d,) in cur.fetchall():
            if d:
                cur.execute(
                    "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
                    (self.user_id, "description", d)
                )
        cur.execute("SELECT DISTINCT usage FROM transactions WHERE user_id = ?", (self.user_id,))
        for (u,) in cur.fetchall():
            if u:
                cur.execute(
                    "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
                    (self.user_id, "usage", u)
                )
        conn.commit()
        conn.close()

    def _add_suggestion(self, text: str, suggestion_type: str):
        if not text:
            return
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO suggestions(user_id, suggestion_type, text) VALUES (?,?,?)",
            (self.user_id, suggestion_type, text)
        )
        conn.commit()
        conn.close()

    def logout(self):
        self.hide()
        if self.login_window:
            self.login_window.reset_fields()
            self.login_window.show()
        else:
            QMessageBox.warning(self, "Fehler", "Kein Login-Fenster verfügbar.")

    def check_dark_mode(self):
        palette = QApplication.instance().palette()
        return palette.color(QPalette.Window).lightness() < 128

    def build_top_ui(self, font):
        # Row 1: action buttons
        btn_row = QHBoxLayout()

        self.logout_btn = QPushButton("Abmelden")
        self.logout_btn.setFont(font)
        self.logout_btn.clicked.connect(self.logout)
        btn_row.addWidget(self.logout_btn)

        fix_btn = QPushButton("Fixkosten")
        fix_btn.setFont(font)
        fix_btn.clicked.connect(self.open_manage_fix_betrage)
        btn_row.addWidget(fix_btn)

        sync_btn = QPushButton("Sync")
        sync_btn.setFont(font)
        sync_btn.clicked.connect(self.trigger_data_load)
        btn_row.addWidget(sync_btn)

        # renamed:
        verw_btn = QPushButton("Verwaltung")
        verw_btn.setFont(font)
        verw_btn.clicked.connect(self.open_manage_suggestions)
        btn_row.addWidget(verw_btn)

        btn_row.addStretch()
        self.main_layout.addLayout(btn_row)

        # Row 2: search / year / month
        filter_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setFont(font)
        self.search_input.setPlaceholderText("Suche Name/Firma oder Verwendungszweck…")
        self.search_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_input.textChanged.connect(self.filter_table)
        filter_row.addWidget(self.search_input, stretch=2)

        filter_row.addWidget(QLabel("Jahr:"))
        self.year_cb = QComboBox()
        self.year_cb.setFont(font)
        self.year_cb.addItems(
            ["Archiv 2020-2024"]
            + [str(y) for y in range(date.today().year - 1, date.today().year + 1)]
        )
        self.year_cb.setCurrentText(str(date.today().year))
        self.year_cb.currentIndexChanged.connect(self.trigger_data_load)
        filter_row.addWidget(self.year_cb)

        filter_row.addWidget(QLabel("Monat:"))
        self.month_cb = QComboBox()
        self.month_cb.setFont(font)
        self.month_cb.addItems(["Alle"] + MONTHS)
        self.month_cb.setCurrentIndex(date.today().month)
        self.month_cb.currentIndexChanged.connect(self.trigger_data_load)
        filter_row.addWidget(self.month_cb)

        self.main_layout.addLayout(filter_row)

    def build_table(self, font):
        self.table = QTableWidget(0, 7)
        self.table.setFont(font)
        self.table.setHorizontalHeaderLabels([
            "Datum", "Beschreibung", "Verwendungszweck",
            "Betrag", "Bezahlt", "ID", "FixID"
        ])
        self.table.setColumnHidden(5, True)
        self.table.setColumnHidden(6, True)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 120)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellClicked.connect(self.handle_cell_click)
        self.main_layout.addWidget(self.table)

    def build_summary_ui(self):
        summary = QHBoxLayout()
        self.balance_lbl = QLabel("Saldo: 0,00 €")
        self.open_lbl = QLabel("")
        bold = QFont(); bold.setPointSize(18); bold.setBold(True)
        self.balance_lbl.setFont(bold)
        self.open_lbl.setFont(bold)
        summary.addWidget(self.balance_lbl)
        summary.addStretch()
        summary.addWidget(self.open_lbl)
        self.main_layout.addLayout(summary)

    def build_input_ui(self, font):
        inp = QHBoxLayout()

        self.desc_input = QComboBox()
        self.desc_input.setEditable(True)
        self.desc_input.setFont(font)
        self.desc_input.lineEdit().setPlaceholderText("Name/Firma")
        desc_completer = QCompleter(self.desc_input.model(), self)
        desc_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.desc_input.setCompleter(desc_completer)
        inp.addWidget(self.desc_input)

        self.usage_input = QComboBox()
        self.usage_input.setEditable(True)
        self.usage_input.setFont(font)
        self.usage_input.lineEdit().setPlaceholderText("Verwendungszweck")
        usage_completer = QCompleter(self.usage_input.model(), self)
        usage_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.usage_input.setCompleter(usage_completer)
        inp.addWidget(self.usage_input)

        self.amount_input = QLineEdit()
        self.amount_input.setFont(font)
        self.amount_input.setPlaceholderText("Betrag (€)")
        self.amount_input.setFixedWidth(150)
        self.amount_input.returnPressed.connect(self.add_transaction)
        inp.addWidget(self.amount_input)

        add_btn = QPushButton("Hinzufügen")
        add_btn.setFont(font)
        add_btn.clicked.connect(self.add_transaction)
        inp.addWidget(add_btn)

        del_btn = QPushButton("Löschen")
        del_btn.setFont(font)
        del_btn.clicked.connect(self.delete_selected_transaction)
        inp.addWidget(del_btn)

        self.main_layout.addLayout(inp)

    def open_manage_fix_betrage(self):
        dlg = ManageFixBetrageDialog(self.user_id, self)
        dlg.exec()
        self.trigger_data_load()

    def open_manage_suggestions(self):
        from ui.dialogs import ManageSuggestionsDialog
        dlg = ManageSuggestionsDialog(self.user_id, self)
        dlg.exec()
        self.trigger_data_load()

    def trigger_data_load(self):
        self.insert_missing_fix_transactions()
        self.load_suggestions()
        year = self.year_cb.currentText()
        month = self.month_cb.currentIndex()
        self.load_thread = LoadDataThread(self.user_id, year, month)
        self.load_thread.dataLoaded.connect(self.update_table)
        self.load_thread.start()

    def load_suggestions(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT text FROM suggestions WHERE user_id = ? AND suggestion_type = 'description' ORDER BY text",
            (self.user_id,)
        )
        descs = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT text FROM suggestions WHERE user_id = ? AND suggestion_type = 'usage' ORDER BY text",
            (self.user_id,)
        )
        usages = [r[0] for r in cur.fetchall()]
        conn.close()

        self.desc_input.blockSignals(True)
        self.desc_input.clear()
        self.desc_input.addItems(descs)
        self.desc_input.setCurrentText("")
        self.desc_input.blockSignals(False)

        self.usage_input.blockSignals(True)
        self.usage_input.clear()
        self.usage_input.addItems(usages)
        self.usage_input.setCurrentText("")
        self.usage_input.blockSignals(False)

    def insert_missing_fix_transactions(self):
        selected_year = self.year_cb.currentText()
        selected_month = self.month_cb.currentIndex()
        if selected_year.startswith("Archiv"):
            return

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, description, usage, amount, duration, start_date "
            "FROM recurring_entries WHERE user_id = ?",
            (self.user_id,)
        )
        fix_entries = cur.fetchall()

        if selected_month == 0:
            months_to_check = range(1, 13)
        else:
            months_to_check = [selected_month]

        cur.execute(
            "SELECT recurring_id, strftime('%Y', date), strftime('%m', date) "
            "FROM transactions WHERE user_id = ? AND recurring_id IS NOT NULL",
            (self.user_id,)
        )
        existing = {(int(r[0]), int(r[1]), int(r[2])) for r in cur.fetchall()}

        inserts = []
        for rec_id, desc, usage, amount, duration, start in fix_entries:
            start_year, start_month, *_ = map(int, start.split("-"))
            for m in months_to_check:
                months_passed = (int(selected_year) - start_year) * 12 + m - start_month
                if months_passed < 0 or months_passed >= duration:
                    continue
                key = (rec_id, int(selected_year), m)
                if key in existing:
                    continue
                inserts.append((
                    self.user_id,
                    date(int(selected_year), m, 1).isoformat(),
                    desc, usage, float(amount), 0, rec_id
                ))

        if inserts:
            cur.executemany(
                "INSERT INTO transactions(user_id, date, description, \"usage\", "
                "amount, paid, recurring_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                inserts
            )
            conn.commit()
        conn.close()

    def update_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        saldo = Decimal('0.0')
        offen = Decimal('0.0')

        for id_, dts, desc, usage, amount, paid, recid in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)

            saldo += Decimal(str(amount))
            yyyy, mm, dd = dts.split('-')
            itm = QTableWidgetItem(f"{dd}.{mm}")
            itm.setData(Qt.EditRole, QDate(int(yyyy), int(mm), int(dd)))
            self.table.setItem(r, 0, itm)

            self.table.setItem(r, 1, QTableWidgetItem(desc))
            self.table.setItem(r, 2, QTableWidgetItem(usage))

            amt_item = QTableWidgetItem(f"{Decimal(str(amount)):.2f} €")
            if amount < 0:
                amt_item.setForeground(QColor("#FF0000"))
                if recid and not paid:
                    offen += Decimal(str(amount))
            else:
                amt_item.setForeground(QColor("#32CD32"))
            self.table.setItem(r, 3, amt_item)

            symbol = (
                "✓" if (recid and amount < 0 and paid)
                else ("✗" if (recid and amount < 0) else "")
            )
            self.table.setItem(r, 4, QTableWidgetItem(symbol))
            self.table.setItem(r, 5, QTableWidgetItem(str(id_)))
            self.table.setItem(r, 6, QTableWidgetItem(str(recid or "")))

        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.AscendingOrder)

        col = "#32CD32" if saldo >= 0 else "#FF0000"
        self.balance_lbl.setText(
            f"Saldo: {saldo:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        self.balance_lbl.setStyleSheet(f"color: {col}; font-weight: bold")

        txt = f"Offen: {offen:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        self.open_lbl.setText(txt)
        oc = (
            '#FF0000' if offen < 0
            else ('#FFFFFF' if self.is_dark_mode else '#000000')
        )
        self.open_lbl.setStyleSheet(f"color: {oc}; font-weight: bold")

    def add_transaction(self):
        desc = self.desc_input.currentText().strip()
        usage = self.usage_input.currentText().strip()
        try:
            amt = float(self.amount_input.text().replace(',', '.'))
        except ValueError:
            QMessageBox.warning(self, "Ungültiger Betrag", "Bitte gültigen Betrag eingeben.")
            return

        dts = date.today().isoformat()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transactions(user_id, date, description, \"usage\", amount, paid) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (self.user_id, dts, desc, usage, amt)
        )
        conn.commit()
        conn.close()

        self._add_suggestion(desc, "description")
        self._add_suggestion(usage, "usage")

        self.desc_input.setCurrentText("")
        self.usage_input.setCurrentText("")
        self.amount_input.clear()

        self.trigger_data_load()

    def delete_selected_transaction(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Keine Auswahl", "Bitte wählen Sie mindestens eine Transaktion.")
            return

        ids = [int(self.table.item(r.row(), 5).text()) for r in sel]
        if QMessageBox.question(
            self, "Löschen bestätigen",
            f"Sollen wirklich {len(ids)} Transaktion(en) gelöscht werden?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        conn = get_db_connection()
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
            if not recid:
                return
            amt = Decimal(
                self.table.item(row, 3).text()
                .replace(' €', '')
                .replace('.', '')
                .replace(',', '.')
            )
            if amt < 0:
                tid = int(self.table.item(row, 5).text())
                paid = self.table.item(row, 4).text() == '✓'
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE transactions SET paid = ? WHERE id = ? AND user_id = ?",
                    (0 if paid else 1, tid, self.user_id)
                )
                conn.commit()
                conn.close()
                self.trigger_data_load()

    def filter_table(self, text):
        text = text.lower()
        highlight = QColor(128, 0, 128, 100)
        for r in range(self.table.rowCount()):
            d_item = self.table.item(r, 1)
            u_item = self.table.item(r, 2)
            d, u = d_item.text().lower(), u_item.text().lower()
            hide = text and text not in d and text not in u
            self.table.setRowHidden(r, hide)
            d_item.setBackground(Qt.NoBrush)
            u_item.setBackground(Qt.NoBrush)
            if text in d:
                d_item.setBackground(highlight)
            if text in u:
                u_item.setBackground(highlight)

    def closeEvent(self, event: QEvent):
        QApplication.instance().quit()
