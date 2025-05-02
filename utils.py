import re
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget

def set_unified_font(widget: QWidget, pt_size: int = 13):
    """
    Setzt für ein Widget (und alle seine Kinder) eine einheitliche
    Punktgröße für die Schriftart.
    """
    font = QFont()
    font.setPointSize(pt_size)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child.setFont(font)

def check_password(password: str) -> (bool, str):
    """
    Prüft, ob das Passwort den folgenden Kriterien entspricht:
    - Mindestens 8 Zeichen
    - Kein Leerzeichen
    - Mindestens ein Großbuchstabe
    - Mindestens ein Kleinbuchstabe
    - Mindestens eine Zahl
    - Mindestens ein Sonderzeichen aus !@#$%^&*(),.?\":{}|<>
    """
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
