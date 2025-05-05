from core.db import init_db

if __name__ == "__main__":
    print("🔧 Initialisiere PostgreSQL-Datenbank ...")
    init_db()
    print("✅ Tabellen erfolgreich erstellt.")
