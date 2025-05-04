import re
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget
from constants import resource_path  # zentrale Pfadfunktion verwenden
# utils.py (Ergänzungen)
import re
from decimal import Decimal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QWidget
from constants import resource_path

def set_unified_font(widget: QWidget, pt_size: int = 13):
    font = QFont()
    font.setPointSize(pt_size)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child.setFont(font)

def check_password(password: str) -> (bool, str):
    if len(password) < 8:
        return False, "Mindestens 8 Zeichen."
    if re.search(r"\s", password):
        return False, "Leerzeichen sind nicht erlaubt."
    if not re.search(r"[A-Z]", password):
        return False, "Mindestens ein Großbuchstabe."
    if not re.search(r"[a-z]", password):
        return False, "Mindestens ein Kleinbuchstabe."
    if not re.search(r"\d", password):
        return False, "Mindestens eine Zahl."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Mindestens ein Sonderzeichen."
    return True, ""

def format_euro(value: Decimal) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def saldo_color(value: Decimal) -> str:
    return "#32CD32" if value >= 0 else "#FF0000"

def open_amount_color(open_sum: Decimal, is_dark_mode: bool) -> str:
    if open_sum < 0:
        return "#FF0000"
    return "#FFFFFF" if is_dark_mode else "#000000"
