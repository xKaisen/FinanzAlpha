import os
from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QMessageBox, QAbstractItemView, QSizePolicy,
    QCompleter, QFrame
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QDate
from PySide6.QtGui import QColor, QFont

from core.db import get_db_connection
from constants import MONTHS
from ui.dialogs import ManageFixBetrageDialog, ManageSuggestionsDialog
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
        cond = ["user_id = %s"]  # %s statt ?
        if self.year.startswith("Archiv"):
            cond.append("to_char(date, 'YYYY') BETWEEN '2020' AND '2024'")  # to_char statt strftime
        else:
            cond.append("to_char(date, 'YYYY') = %s")  # to_char statt strftime
            params.append(self.year)
            if self.month > 0:
                cond.append("to_char(date, 'MM') = %s")  # to_char statt strftime
                params.append(f"{self.month:02d}")

        sql = f"""
            SELECT id, date, description, "usage", amount, paid, recurring_id
            FROM transactions
            WHERE {' AND '.join(cond)}
            ORDER BY date ASC
        """
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        self.dataLoaded.emit(rows)

class Dashboard(QWidget):
    def __init__(self, user_id, parent=None):
        super().__init__(parent)

        # Global stylesheet mit modernem Table-Design
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: white;
            }

            QLabel {
                background-color: transparent;
            }

            /* Buttons */
            QPushButton {
                background-color: #1ed760;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 12pt;
                margin: 4px;
            }
            QPushButton:hover {
                background-color: #42e47f;
            }
            QPushButton:pressed {
                background-color: #17b350;
            }

            /* Inputs & Combobox */
            QLineEdit, QComboBox {
                background-color: #3b3b3b;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px 12px;
                color: white;
                font-size: 13pt;
            }

            QComboBox::drop-down {
                border: none;
                width: 20px;
            }

            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }

            QComboBox QAbstractItemView {
                background-color: #3b3b3b;
                border: 1px solid #555;
                selection-background-color: #555;
            }

            /* Tabelle: Moderne Gestaltung */
            QTableWidget {
                background-color: #2e2e2e;
                alternate-background-color: #333333;
                border: none;
                border-radius: 12px;
                gridline-color: transparent;
                padding: 10px;
                selection-background-color: #444444;
            }

            /* Tabellen-Header: Modern und auffällig */
            QHeaderView::section {
                background-color: #333333;
                color: white;
                padding: 12px 8px;
                border: none;
                border-bottom: 2px solid #1ed760;
                font-weight: bold;
                font-size: 12pt;
            }

            QHeaderView::section:first {
                border-top-left-radius: 8px;
            }

            QHeaderView::section:last {
                border-top-right-radius: 8px;
            }

            /* Tabellen-Zeilen: Moderne Effekte */
            QTableWidget::item {
                border-bottom: 1px solid #3a3a3a;
                padding: 8px;
                margin: 2px;
            }

            QTableWidget::item:hover {
                background-color: #3a3a3a;
                border-radius: 6px;
            }

            QTableWidget::item:selected {
                background-color: #444444;
                border-radius: 6px;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 10px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background: #555;
                min-height: 20px;
                border-radius: 5px;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                background-color: #2b2b2b;
                height: 10px;
                margin: 0px;
            }

            QScrollBar::handle:horizontal {
                background: #555;
                min-width: 20px;
                border-radius: 5px;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        self.user_id = user_id
        self.login_window = None

        # Vorschlags-Tabelle initialisieren
        self._ensure_suggestions_table()
        self._seed_suggestions_from_existing_transactions()

        # Basis-Schriftart
        base_font = QFont()
        base_font.setPointSize(15)
        QApplication.instance().setFont(base_font)

        self.setWindowTitle(f"FinanzApp Alpha {__version__}")
        self.setMinimumSize(1000, 700)

        # Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # UI-Bausteine
        self.build_top_ui(base_font)
        self.build_table(base_font)
        self.build_summary_ui()
        self.build_footer_ui()

        # Daten-Neulade-Timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.trigger_data_load)
        self.trigger_data_load()

    def _ensure_suggestions_table(self):
        conn = get_db_connection()
        cur = conn.cursor()
        # PostgreSQL syntax for CREATE TABLE IF NOT EXISTS
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
        cur.execute("SELECT DISTINCT description FROM transactions WHERE user_id = %s", (self.user_id,))
        for (d,) in cur.fetchall():
            if d:
                cur.execute(
                    "INSERT INTO suggestions(user_id, suggestion_type, text) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (self.user_id, "description", d)
                )
        cur.execute("SELECT DISTINCT usage FROM transactions WHERE user_id = %s", (self.user_id,))
        for (u,) in cur.fetchall():
            if u:
                cur.execute(
                    "INSERT INTO suggestions(user_id, suggestion_type, text) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (self.user_id, "usage", u)
                )
        conn.commit()
        conn.close()

    def _add_suggestion(self, text, suggestion_type):
        if not text:
            return
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO suggestions(user_id, suggestion_type, text) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (self.user_id, suggestion_type, text)
        )
        conn.commit()
        conn.close()

    def logout(self):
        self.close()
        if self.login_window:
            self.login_window.reset_fields()
            self.login_window.show()

    def open_manage_fix_betrage(self):
        dlg = ManageFixBetrageDialog(self.user_id, self)
        dlg.exec()
        self.trigger_data_load()

    def open_manage_suggestions(self):
        dlg = ManageSuggestionsDialog(self.user_id, self)
        dlg.exec()
        self.trigger_data_load()

    def build_top_ui(self, font):
        row1 = QHBoxLayout()
        for text, slot in [
            ("Abmelden", self.logout),
            ("Fixkosten", self.open_manage_fix_betrage),
            ("Sync", self.trigger_data_load),
            ("Verwaltung", self.open_manage_suggestions),
        ]:
            btn = QPushButton(text)
            btn.setFont(font)
            btn.clicked.connect(slot)
            row1.addWidget(btn)
        row1.addSpacing(20)

        self.search_input = QLineEdit()
        self.search_input.setFont(font)
        self.search_input.setPlaceholderText("Suche…")
        self.search_input.textChanged.connect(self.filter_table)
        row1.addWidget(self.search_input, 2)

        # Dropdown-Container mit dunklem Design
        dropdown_frame = QFrame()
        dropdown_frame.setStyleSheet("""
            QFrame {
                background-color: #333333;
                border-radius: 8px;
                padding: 4px;
            }
            QLabel {
                color: #cccccc;
                padding: 0 4px;
            }
        """)

        dropdown_layout = QHBoxLayout(dropdown_frame)
        dropdown_layout.setContentsMargins(4, 4, 4, 4)
        dropdown_layout.setSpacing(8)

        # Jahr Dropdown
        year_label = QLabel("Jahr:")
        dropdown_layout.addWidget(year_label)

        self.year_cb = QComboBox()
        self.year_cb.setFont(font)
        self.year_cb.addItems(["Archiv 2020-2024"] + [str(y) for y in range(2020, 2041)])
        self.year_cb.setCurrentText(str(date.today().year))
        self.year_cb.currentIndexChanged.connect(self.trigger_data_load)
        self.year_cb.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 100px;
            }
            QComboBox:hover {
                border-color: #555;
            }
            QComboBox::drop-down {
                width: 24px;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                selection-background-color: #444;
            }
        """)
        dropdown_layout.addWidget(self.year_cb)

        # Monat Dropdown
        month_label = QLabel("Monat:")
        dropdown_layout.addWidget(month_label)

        self.month_cb = QComboBox()
        self.month_cb.setFont(font)
        self.month_cb.addItems(["Alle"] + MONTHS)
        self.month_cb.setCurrentIndex(date.today().month)
        self.month_cb.currentIndexChanged.connect(self.trigger_data_load)
        self.month_cb.setStyleSheet(self.year_cb.styleSheet())
        dropdown_layout.addWidget(self.month_cb)

        row1.addWidget(dropdown_frame)
        row1.addStretch()
        self.main_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.desc_input = QComboBox()
        self.desc_input.setEditable(True)
        self.desc_input.setFont(font)
        self.desc_input.lineEdit().setPlaceholderText("Name/Firma")
        self.desc_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.desc_input.setCompleter(QCompleter(self.desc_input.model(), self))
        row2.addWidget(self.desc_input, 2)

        self.usage_input = QComboBox()
        self.usage_input.setEditable(True)
        self.usage_input.setFont(font)
        self.usage_input.lineEdit().setPlaceholderText("Verwendungszweck")
        self.usage_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.usage_input.setCompleter(QCompleter(self.usage_input.model(), self))
        row2.addWidget(self.usage_input, 2)

        self.amount_input = QLineEdit()
        self.amount_input.setFont(font)
        self.amount_input.setPlaceholderText("Betrag (€)")
        self.amount_input.setFixedWidth(140)
        self.amount_input.returnPressed.connect(self.add_transaction)
        row2.addWidget(self.amount_input)

        btn_add = QPushButton("Hinzufügen")
        btn_add.setFont(font)
        btn_add.clicked.connect(self.add_transaction)
        row2.addWidget(btn_add)

        btn_del = QPushButton("Löschen")
        btn_del.setFont(font)
        btn_del.clicked.connect(self.delete_selected_transaction)
        row2.addWidget(btn_del)

        row2.addStretch()
        self.main_layout.addLayout(row2)

    def build_table(self, font):
        self.table = QTableWidget(0, 7)
        self.table.setFont(font)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setHorizontalHeaderLabels(
            ["Datum", "Beschreibung", "Verwendungszweck", "Betrag", "Bezahlt", "ID", "FixID"]
        )
        for col in (5, 6):
            self.table.setColumnHidden(col, True)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 120)
        for i in (1, 2):
            hdr.setSectionResizeMode(i, QHeaderView.Stretch)
        for i in (3, 4):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellClicked.connect(self.handle_cell_click)
        self.table.setContentsMargins(10, 10, 10, 10)

        self.main_layout.addWidget(self.table)

    def build_summary_ui(self):
        lay = QHBoxLayout()

        self.balance_lbl = QLabel("Saldo: 0,00 €")
        bold = QFont()
        bold.setPointSize(18)
        bold.setBold(True)
        self.balance_lbl.setFont(bold)
        self.balance_lbl.setStyleSheet("padding: 8px; border-radius: 8px;")

        self.open_lbl = QLabel("")
        self.open_lbl.setFont(bold)
        self.open_lbl.setStyleSheet("padding: 8px; border-radius: 8px;")

        lay.addWidget(self.balance_lbl)
        lay.addStretch()
        lay.addWidget(self.open_lbl)
        self.main_layout.addLayout(lay)

    def build_footer_ui(self):
        footer = QHBoxLayout()
        lbl1 = QLabel(f"Version {__version__}")
        lbl2 = QLabel("© 2025 xKAISEN. Alle Rechte vorbehalten.")
        footer.addWidget(lbl1)
        footer.addStretch()
        footer.addWidget(lbl2)
        self.main_layout.addLayout(footer)

    def trigger_data_load(self):
        self.insert_missing_fix_transactions()
        self.load_suggestions()
        year = self.year_cb.currentText()
        month = self.month_cb.currentIndex()
        self.load_thread = LoadDataThread(self.user_id, year, month)
        self.load_thread.dataLoaded.connect(self.update_table)
        self.load_thread.start()

    def insert_missing_fix_transactions(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, description, usage, amount, duration, start_date "
            "FROM recurring_entries WHERE user_id=%s",
            (self.user_id,)
        )
        fix_entries = cur.fetchall()
        sel_year = self.year_cb.currentText()
        sel_month = self.month_cb.currentIndex()
        months = range(1, 13) if sel_month == 0 else [sel_month]

        cur.execute(
            "SELECT recurring_id, to_char(date, 'YYYY'), to_char(date, 'MM') "
            "FROM transactions WHERE user_id=%s AND recurring_id IS NOT NULL",
            (self.user_id,)
        )
        existing = {(int(r[0]), int(r[1]), int(r[2])) for r in cur.fetchall()}

        inserts = []
        for rec_id, desc, usage, amount, duration, start in fix_entries:
            sy, sm, _ = start.year, start.month, start.day  # Extract year, month, and day directly
            for m in months:
                mp = (int(sel_year) - sy) * 12 + m - sm
                if mp < 0 or mp >= duration:
                    continue
                key = (rec_id, int(sel_year), m)
                if key in existing:
                    continue
                inserts.append((
                    self.user_id,
                    date(int(sel_year), m, 1).isoformat(),
                    desc, usage, float(amount), False, rec_id  # Use False for paid
                ))

        if inserts:
            cur.executemany(
                "INSERT INTO transactions(user_id, date, description, \"usage\", amount, paid, recurring_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                inserts
            )
            conn.commit()
        conn.close()

    def load_suggestions(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT text FROM suggestions WHERE user_id=%s AND suggestion_type='description' ORDER BY text",
            (self.user_id,)
        )
        descs = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT text FROM suggestions WHERE user_id=%s AND suggestion_type='usage' ORDER BY text",
            (self.user_id,)
        )
        usages = [r[0] for r in cur.fetchall()]
        conn.close()

        for combo, items in [(self.desc_input, descs), (self.usage_input, usages)]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(items)
            combo.setCurrentText("")
            combo.blockSignals(False)

    def update_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        saldo = Decimal("0.0")
        offen = Decimal("0.0")
        bold_font = QFont()
        bold_font.setBold(True)

        for id_, dts, desc, usage, amount, paid, recid in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            saldo += Decimal(str(amount))

            yyyy, mm, dd = dts.year, dts.month, dts.day  # Extract year, month, and day directly
            date_item = QTableWidgetItem(f"{dd:02d}.{mm:02d}")
            date_item.setData(Qt.EditRole, QDate(yyyy, mm, dd))
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, date_item)

            desc_item = QTableWidgetItem(desc)
            usage_item = QTableWidgetItem(usage)
            self.table.setItem(r, 1, desc_item)
            self.table.setItem(r, 2, usage_item)

            amt_item = QTableWidgetItem(f"{Decimal(str(amount)):.2f} €")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if amount < 0:
                amt_item.setForeground(QColor("#ff6b6b"))
                amt_item.setFont(bold_font)
                if recid and not paid:
                    offen += Decimal(str(amount))
            else:
                amt_item.setForeground(QColor("#4ecdc4"))
            self.table.setItem(r, 3, amt_item)

            sym = ""
            if recid and amount < 0:
                if paid:
                    sym = "✓"
                    paid_item = QTableWidgetItem(sym)
                    paid_item.setForeground(QColor("#4ecdc4"))
                else:
                    sym = "✗"
                    paid_item = QTableWidgetItem(sym)
                    paid_item.setForeground(QColor("#ff6b6b"))
                paid_item.setTextAlignment(Qt.AlignCenter)
                paid_item.setFont(bold_font)
                self.table.setItem(r, 4, paid_item)
            else:
                paid_item = QTableWidgetItem(sym)
                paid_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 4, paid_item)

            self.table.setItem(r, 5, QTableWidgetItem(str(id_)))
            self.table.setItem(r, 6, QTableWidgetItem(str(recid or "")))

        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.AscendingOrder)

        col = "#32CD32" if saldo >= 0 else "#FF0000"
        saldo_text = f"Saldo: {saldo:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        self.balance_lbl.setText(saldo_text)
        self.balance_lbl.setStyleSheet(
            f"color:{col}; font-weight:bold; background-color: #333333; padding: 10px; border-radius: 8px;")

        if offen < 0:
            offen_text = f"Offen: {offen:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
            self.open_lbl.setText(offen_text)
            self.open_lbl.setStyleSheet(
                f"color:#FF0000; font-weight:bold; background-color: #333333; padding: 10px; border-radius: 8px;")
        else:
            self.open_lbl.setText("")

    def add_transaction(self):
        desc = self.desc_input.currentText().strip()
        usage = self.usage_input.currentText().strip()
        try:
            amt = float(self.amount_input.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Ungültiger Betrag", "Bitte gültigen Betrag eingeben.")
            return

        dts = date.today().isoformat()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transactions(user_id, date, description, \"usage\", amount, paid) VALUES (%s, %s, %s, %s, %s, TRUE)",
            (self.user_id, dts, desc, usage, amt),
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
                self, "Löschen bestätigen", f"Sollen wirklich {len(ids)} Transaktion(en) gelöscht werden?",
                QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        conn = get_db_connection()
        cur = conn.cursor()
        for tid in ids:
            cur.execute(
                "DELETE FROM transactions WHERE id = %s AND user_id = %s",
                (tid, self.user_id)
            )
        conn.commit()
        conn.close()
        self.trigger_data_load()

    def handle_cell_click(self, row, col):
        if col != 4:
            return
        recid = int(self.table.item(row, 6).text() or 0)
        if not recid:
            return

        amt = Decimal(
            self.table.item(row, 3).text().replace(" €", "").replace(".", "").replace(",", ".")
        )
        if amt >= 0:
            return

        tid = int(self.table.item(row, 5).text())
        paid = self.table.item(row, 4).text() == "✓"
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE transactions SET paid = %s WHERE id = %s AND user_id = %s",
            (not paid, tid, self.user_id),
        )
        conn.commit()
        conn.close()
        self.trigger_data_load()

    def filter_table(self, text):
        text = text.lower()
        highlight = QColor(128, 128, 128, 50)
        for r in range(self.table.rowCount()):
            d_item = self.table.item(r, 1)
            u_item = self.table.item(r, 2)
            td, tu = d_item.text().lower(), u_item.text().lower()
            hide = text and text not in td and text not in tu
            self.table.setRowHidden(r, hide)
            d_item.setBackground(Qt.NoBrush)
            u_item.setBackground(Qt.NoBrush)
            if text in td:
                d_item.setBackground(highlight)
            if text in tu:
                u_item.setBackground(highlight)

    def closeEvent(self, event):
        QApplication.instance().quit()
