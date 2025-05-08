import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, scoped_session

from core.models import Base

load_dotenv()

MODE         = os.getenv("APP_MODE", "online").lower()
SQLITE_PATH  = os.getenv("SQLITE_PATH", "local.db")
POSTGRES_URL = os.getenv("DATABASE_URL")

if MODE == "offline":
    DB_URL = f"sqlite:///{SQLITE_PATH}"
elif not POSTGRES_URL:
    raise RuntimeError("DATABASE_URL nicht gesetzt – bitte in .env eintragen.")
else:
    DB_URL = POSTGRES_URL

engine = create_engine(DB_URL, echo=False)

try:
    Base.metadata.create_all(engine)
    logging.info(f"Datenbank initialisiert: {DB_URL}")
except OperationalError as e:
    logging.warning(f"Remote-DB nicht erreichbar ({DB_URL}): {e}")
    if MODE != "offline":
        fallback = f"sqlite:///{SQLITE_PATH}"
        engine = create_engine(fallback, echo=False)
        Base.metadata.create_all(engine)
        logging.info(f"SQLite-Fallback initialisiert: {fallback}")
    else:
        logging.error("Offline-Modus aktiv, kann SQLite-DB nicht anlegen.", exc_info=True)
        raise

Session = scoped_session(sessionmaker(bind=engine))

def get_db_connection():
    return engine.raw_connection()

def init_db():
    Base.metadata.create_all(engine)
