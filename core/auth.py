import bcrypt
import hashlib
from core.db import get_db_connection
from utils import check_password

# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

def login_user(username: str, password: str):
    """
    Rückgabe:
        (True, (user_id, is_admin_bool))  bei Erfolg
        (False, "Fehlermeldung")          bei Fehler
    """
    conn = get_db_connection()
    cur  = conn.cursor()

    cur.execute(
        "SELECT id, password_hash, COALESCE(is_admin,0) AS is_admin "
        "FROM users WHERE lower(username) = lower(?)",
        (username,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, "Benutzername oder Passwort falsch"

    # Extrahiere je nach Rückgabeformat
    user_id, stored_hash, is_admin = (
        (row["id"], row["password_hash"], row["is_admin"])
        if hasattr(row, "keys") else row
    )

    # Wenn kein Hash vorhanden ist, Fehler abfangen
    if not stored_hash:
        conn.close()
        return False, "Interner Fehler: kein Passwort‑Hash hinterlegt"

    # ── bcrypt-Hash prüfen ────────────────────────────────────────────────────
    if str(stored_hash).startswith("$2"):
        try:
            if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                conn.close()
                return True, (user_id, bool(is_admin))
        except ValueError:
            conn.close()
            return False, "Interner Fehler bei der Hash‑Prüfung"
        conn.close()
        return False, "Benutzername oder Passwort falsch"

    # ── Legacy SHA-256 prüfen ─────────────────────────────────────────────────
    try:
        sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    except Exception:
        conn.close()
        return False, "Interner Fehler bei der Hash‑Berechnung"

    if sha256_hash == stored_hash:
        # Upgrade auf bcrypt
        try:
            new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id)
            )
            conn.commit()
        except Exception:
            # Falls Upgrade schiefgeht, ignorieren wir es und lassen Legacy-Login zu
            pass
        finally:
            conn.close()
        return True, (user_id, bool(is_admin))

    conn.close()
    return False, "Benutzername oder Passwort falsch"


# ---------------------------------------------------------------------------
# REGISTRIERUNG
# ---------------------------------------------------------------------------

def register_user(username: str, password: str, is_admin: bool = False):
    """
    Legt einen neuen Benutzer an.
    * Nur ein Admin-Account ist erlaubt (is_admin=True schlägt fehl, falls bereits ein Admin existiert).
    Liefert (True, "OK") oder (False, "Fehlertext").
    """
    # Passwortpolicy prüfen
    valid, msg = check_password(password)
    if not valid:
        return False, msg

    conn = get_db_connection()
    cur  = conn.cursor()

    # 1) Existiert der Benutzername bereits?
    cur.execute("SELECT 1 FROM users WHERE lower(username)=lower(?)", (username,))
    if cur.fetchone():
        conn.close()
        return False, "Benutzer existiert bereits."

    # 2) Darf ein weiterer Admin angelegt werden?
    if is_admin:
        cur.execute("SELECT 1 FROM users WHERE is_admin = 1")
        if cur.fetchone():
            conn.close()
            return False, "Es existiert bereits ein Admin-Account."

    # 3) Passwort-Hash erzeugen
    try:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except Exception as e:
        conn.close()
        return False, f"Fehler beim Hashen des Passworts: {e}"

    # 4) Neuen User eintragen
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, pw_hash, int(is_admin))
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Datenbankfehler bei Registrierung: {e}"
    finally:
        conn.close()

    return True, "Registrierung erfolgreich"
