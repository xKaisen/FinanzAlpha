from datetime import datetime
from typing import Tuple, Union

import bcrypt
import hashlib
from sqlalchemy.exc import IntegrityError

from core.db import Session
from core.models import User
from utils import check_password


def login_user(username: str, password: str) -> Tuple[bool, Union[str, Tuple[int, bool]]]:
    session = Session()
    try:
        user = session.query(User).filter(User.username.ilike(username)).first()
        if not user:
            return False, "Benutzername oder Passwort falsch"

        stored = user.password_hash or ""
        if stored.startswith("$2"):
            if not bcrypt.checkpw(password.encode(), stored.encode()):
                return False, "Benutzername oder Passwort falsch"
        else:
            if hashlib.sha256(password.encode()).hexdigest() != stored:
                return False, "Benutzername oder Passwort falsch"
            # Migration
            new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user.password_hash = new_hash
            session.commit()

        return True, (user.id, user.is_admin)
    except Exception as e:
        session.rollback()
        return False, f"Login-Fehler: {e}"
    finally:
        session.close()


def register_user(username: str, password: str, is_admin: bool = False) -> Tuple[bool, str]:
    valid, msg = check_password(password)
    if not valid:
        return False, msg

    session = Session()
    try:
        if is_admin:
            if session.query(User).filter_by(is_admin=True).first():
                return False, "Es existiert bereits ein Admin-Account."

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            username=username,
            password_hash=pw_hash,
            is_admin=is_admin,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(user)
        session.commit()
        return True, "Registrierung erfolgreich"
    except IntegrityError:
        session.rollback()
        return False, "Benutzername bereits vergeben."
    except Exception as e:
        session.rollback()
        return False, f"Registrierungsfehler: {e}"
    finally:
        session.close()


def change_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
    valid, msg = check_password(new_password)
    if not valid:
        return False, msg

    session = Session()
    try:
        user = session.get(User, user_id)
        if not user:
            return False, "Benutzer nicht gefunden"
        if not bcrypt.checkpw(old_password.encode(), user.password_hash.encode()):
            return False, "Altes Passwort ist falsch"

        user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        user.updated_at = datetime.utcnow()
        session.commit()
        return True, "Passwort erfolgreich geändert"
    except Exception as e:
        session.rollback()
        return False, f"Fehler beim Passwortwechsel: {e}"
    finally:
        session.close()
