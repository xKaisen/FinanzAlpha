import bcrypt
import hashlib
from db import get_db_connection
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
    conn   = get_db_connection()
    cur    = conn.cursor()

    cur.execute(
        "SELECT id, password_hash, COALESCE(is_admin,0) AS is_admin "
        "FROM users WHERE lower(username) = lower(?)",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Benutzername oder Passwort falsch"

    user_id, stored_hash, is_admin = (
        (row["id"], row["password_hash"], row["is_admin"])
        if hasattr(row, "keys") else row
    )

    # ── bcrypt ─────────────────────────────────────────────────────────────
    if str(stored_hash).startswith("$2"):
        if bcrypt.checkpw(password.encode(), stored_hash.encode()):
            conn.close()
            return True, (user_id, bool(is_admin))
        conn.close()
        return False, "Benutzername oder Passwort falsch"

    # ── Legacy SHA-256 ─────────────────────────────────────────────────────
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    if sha256_hash == stored_hash:
        # Upgrade auf bcrypt
        new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )
        conn.commit()
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
    * Nur **ein** Admin-Account ist erlaubt.  is_admin=True schlägt fehl,
      wenn bereits ein Admin existiert.
    * Liefert (True, "OK") oder (False, "Fehlertext").
    """
    valid, msg = check_password(password)
    if not valid:
        return False, msg

    conn   = get_db_connection()
    cur    = conn.cursor()

    # 1) Existiert der Benutzername bereits? (case-insensitive)
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

    # 3) Eintragen
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, pw_hash, int(is_admin))
    )
    conn.commit()
    conn.close()
    return True, "Registrierung erfolgreich"
