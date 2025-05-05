import bcrypt
import hashlib
from typing import Tuple, Union
from core.db import get_db_connection
from utils import check_password


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

def login_user(username: str, password: str) -> Tuple[bool, Union[str, Tuple[int, bool]]]:
    """
    Authentifiziert einen Benutzer

    Args:
        username: Der Benutzername
        password: Das Klartext-Passwort

    Returns:
        Tuple: (success, message_or_data)
               - success: True wenn erfolgreich
               - message_or_data: Fehlermeldung oder (user_id, is_admin)
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Benutzerdaten abrufen (case-insensitive)
        cur.execute(
            "SELECT id, password_hash, COALESCE(is_admin, false) AS is_admin "
            "FROM users WHERE lower(username) = lower(%s)",
            (username,)
        )
        row = cur.fetchone()

        if not row:
            return False, "Benutzername oder Passwort falsch"

        user_id, stored_hash, is_admin = row

        if not stored_hash:
            return False, "Interner Fehler: kein Passwort-Hash hinterlegt"

        # BCrypt Hash (neues Format)
        if str(stored_hash).startswith("$2"):
            if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                return True, (user_id, is_admin)
            return False, "Benutzername oder Passwort falsch"

        # Legacy SHA256 Hash (Migration)
        sha256_hash = hashlib.sha256(password.encode()).hexdigest()
        if sha256_hash == stored_hash:
            # Auf BCrypt migrieren
            new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_hash, user_id)
            )
            conn.commit()
            return True, (user_id, is_admin)

        return False, "Benutzername oder Passwort falsch"

    except Exception as e:
        return False, f"Login-Fehler: {str(e)}"
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# REGISTRIERUNG
# ---------------------------------------------------------------------------

def register_user(username: str, password: str, is_admin: bool = False) -> Tuple[bool, str]:
    """
    Registriert einen neuen Benutzer

    Args:
        username: Der gewünschte Benutzername
        password: Das Klartext-Passwort
        is_admin: Ob der Benutzer Admin-Rechte erhalten soll

    Returns:
        Tuple: (success, message)
    """
    # Passwortvalidierung
    valid, msg = check_password(password)
    if not valid:
        return False, msg

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Existenzprüfung (case-insensitive)
        cur.execute(
            "SELECT 1 FROM users WHERE lower(username) = lower(%s)",
            (username,)
        )
        if cur.fetchone():
            return False, "Benutzer existiert bereits."

        # Einmaliger Admin-Check
        if is_admin:
            cur.execute("SELECT 1 FROM users WHERE is_admin = TRUE LIMIT 1")
            if cur.fetchone():
                return False, "Es existiert bereits ein Admin-Account."

        # Passwort hashen
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Benutzer anlegen
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin) "
            "VALUES (%s, %s, %s)",
            (username, pw_hash, is_admin)
        )
        conn.commit()
        return True, "Registrierung erfolgreich"

    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"Registrierungsfehler: {str(e)}"
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# HILFSFUNKTIONEN
# ---------------------------------------------------------------------------

def change_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    Ändert das Passwort eines Benutzers

    Args:
        user_id: Die ID des Benutzers
        old_password: Das aktuelle Passwort
        new_password: Das neue Passwort

    Returns:
        Tuple: (success, message)
    """
    valid, msg = check_password(new_password)
    if not valid:
        return False, msg

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Aktuellen Hash abrufen
        cur.execute(
            "SELECT password_hash FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()

        if not row:
            return False, "Benutzer nicht gefunden"

        stored_hash = row[0]

        # Passwort verifizieren
        if not bcrypt.checkpw(old_password.encode(), stored_hash.encode()):
            return False, "Aktuelles Passwort ist falsch"

        # Neuen Hash generieren
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        # Passwort aktualisieren
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, user_id)
        )
        conn.commit()
        return True, "Passwort erfolgreich geändert"

    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"Fehler beim Passwortwechsel: {str(e)}"
    finally:
        if conn:
            conn.close()