# api/__init__.py

# Importiere hier die Objekte, die in app.py registriert werden sollen:
from .routes import api       # dein Flask‑RESTX Api-Objekt
from .sync import sync_bp     # dein Sync‑Blueprint

# Optional: __all__ sorgt dafür, dass „from api import *“ nur diese liefert:
__all__ = ['api', 'sync_bp']