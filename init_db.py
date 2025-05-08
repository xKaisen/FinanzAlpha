import os, sys
# Projekt-Root am Anfang des Suchpfads
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from core.models import Base, LocalChange  # Modelle aus core/models.py

# Lokale SQLite-DB
engine = create_engine('sqlite:///local.db', echo=True)
Base.metadata.create_all(engine)

# Session-Factory
db_session = scoped_session(sessionmaker(bind=engine))
Session = db_session
