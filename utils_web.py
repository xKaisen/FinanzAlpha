# utils.py
from typing import Tuple
from decimal import Decimal
import re
from datetime import date

def check_password(password: str) -> Tuple[bool, str]:
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

def format_euro(value) -> str:
    try:
        value = Decimal(value)
        # deutsche Formatierung 1.234,56 €
        return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "Ungültiger Betrag"

def parse_decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ".").strip())
    except Exception:
        return None

def extract_year_month(d: date) -> Tuple[int, int]:
    return d.year, d.month

def saldo_color(value: Decimal) -> str:
    return "#32CD32" if value >= 0 else "#FF0000"

def open_amount_color(open_sum: Decimal, is_dark_mode: bool) -> str:
    if open_sum < 0:
        return "#FF0000"
    return "#FFFFFF" if is_dark_mode else "#000000"
