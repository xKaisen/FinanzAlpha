import os
from dotenv import load_dotenv  # .env-Datei laden
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# ─── 1. .env-Datei laden ───────────────────────────────────────
load_dotenv()

# ─── 2. PostgreSQL-Verbindungs-URL auslesen ────────────────────
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL nicht gesetzt – bitte in .env eintragen.")

# ─── 3. SQLAlchemy Engine und Session erstellen ────────────────
engine = create_engine(DB_URL, echo=False)
Session = scoped_session(sessionmaker(bind=engine))

# ─── 4. Direkte Verbindung (optional) ──────────────────────────
def get_db_connection():
    """
    Gibt eine rohe DB-Verbindung zurück (z. B. für Low-Level-Zugriffe).
    """
    return engine.raw_connection()

# ─── 5. Tabellen initialisieren ────────────────────────────────
def init_db():
    """
    Erstellt alle Tabellen gemäß core/models.py.
    """
    from core.models import Base
    Base.metadata.create_all(engine)
