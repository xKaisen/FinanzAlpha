# core/fixkosten.py
from core.db import get_db_connection
from datetime import date
from dateutil.relativedelta import relativedelta # Importiere relativedelta für Datumsberechnungen
import logging # Importiere Logging

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO)

def insert_missing_fix_transactions(user_id: int, year: int, month: int):
    """
    Füge für das gegebene Jahr/Monat alle fehlenden Fixkosten-Transaktionen
    ein, basierend auf start_date und duration (1–12 Monate).
    Diese Funktion wird typischerweise beim Laden des Dashboards aufgerufen,
    um sicherzustellen, dass alle erwarteten monatlichen Transaktionen existieren.
    """
    conn = None # Initialisiere conn auf None
    try:
        conn = get_db_connection()
        cur  = conn.cursor()

        logging.info(f"Checking for missing fix transactions for user {user_id}, year {year}, month {month}")

        # Hole alle fixkosten-Einträge des Nutzers
        cur.execute("""
            SELECT id, description, "usage", amount, duration, start_date
              FROM recurring_entries
             WHERE user_id = %s
        """, (user_id,))
        recurring_entries = cur.fetchall()
        logging.info(f"Found {len(recurring_entries)} recurring entries for user {user_id}")

        for rec_id, desc, usage, amount, duration, start_date in recurring_entries:
            # Berechne, wie viele Monate seit start_date bis (year,month) vergangen sind
            # Stelle sicher, dass start_date ein date-Objekt ist (kommt so aus der DB)
            if not isinstance(start_date, date):
                 logging.error(f"start_date for recurring_entry {rec_id} is not a date object: {start_date}")
                 continue # Überspringe diesen Eintrag, wenn start_date ungültig ist

            try:
                # Erstelle ein Datumsobjekt für den ersten Tag des Startmonats
                start_month_date = date(start_date.year, start_date.month, 1)
                # Erstelle ein Datumsobjekt für den ersten Tag des Zielmonats
                target_month_date = date(year, month, 1)

                # Berechne die Differenz in Monaten
                months_since_start = (target_month_date.year - start_month_date.year) * 12 + (target_month_date.month - start_month_date.month)

            except ValueError as e:
                logging.error(f"Error calculating date difference for recurring_entry {rec_id}: {e}")
                continue # Überspringe diesen Eintrag bei Datumsfehler

            # Nur einfügen, wenn die Transaktion innerhalb der Dauer liegt (0-basiert)
            # und der Zielmonat nicht vor dem Startmonat liegt, es sei denn, die Dauer ist 0 (was nicht erlaubt sein sollte, aber als Sicherheit)
            if 0 <= months_since_start < duration:
                # Das Datum für die Transaktion ist der erste Tag des Zielmonats
                entry_date = date(year, month, 1).isoformat()

                # Füge die Transaktion ein. Setze 'paid' auf FALSE.
                # ON CONFLICT vermeidet Duplikate, falls die Funktion mehrmals aufgerufen wird
                insert_query = """
                    INSERT INTO transactions
                      (user_id, date, description, "usage", amount, paid, recurring_id)
                    VALUES (%s, %s, %s, %s, %s, FALSE, %s) -- HIER GEÄNDERT: TRUE zu FALSE
                    ON CONFLICT (user_id, recurring_id, date) DO NOTHING
                """
                insert_params = (user_id, entry_date, desc, usage, amount, rec_id)
                # logging.debug(f"Inserting missing transaction for recurring_entry {rec_id} on {entry_date}") # Zu detailliert für INFO
                cur.execute(insert_query, insert_params)
                # Optional: Logge die eingefügte Transaktion (nur wenn tatsächlich eingefügt)
                # if cur.rowcount > 0:
                #    logging.info(f"Inserted missing transaction for recurring_entry {rec_id} on {entry_date}")


        conn.commit()
        logging.info(f"Finished checking for missing fix transactions for user {user_id}, year {year}, month {month}")

    except Exception as e:
        logging.exception(f"An error occurred in insert_missing_fix_transactions for user {user_id}, year {year}, month {month}:")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def create_fix_transactions(user_id: int, rec_id: int, start_date: date, amount: float, duration: int):
    """
    Erstellt die anfänglichen Transaktionen für eine neue Fixkosten-Serie.
    Diese Funktion wird beim Anlegen einer neuen Fixkosten-Serie aufgerufen.
    """
    conn = None # Initialisiere conn auf None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        logging.info(f"Creating {duration} fix transactions for recurring_entry {rec_id}, starting {start_date}")

        # Stelle sicher, dass start_date der erste Tag des Monats ist
        current_date = start_date.replace(day=1)

        for i in range(duration):
            # Berechne das Datum für die aktuelle Transaktion (erster Tag des Monats)
            transaction_date = current_date + relativedelta(months=i)

            # Füge die Transaktion ein. Setze 'paid' auf FALSE.
            insert_query = """
                INSERT INTO transactions
                  (user_id, date, description, "usage", amount, paid, recurring_id)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s) -- Setze paid auf FALSE für neue Fixkosten
                ON CONFLICT (user_id, recurring_id, date) DO NOTHING -- Vermeide Duplikate
            """
            # Holen Sie Beschreibung und Verwendungszweck aus recurring_entries, da sie hier nicht übergeben werden
            # oder passen Sie die Funktion an, um desc und usage zu übergeben, falls verfügbar.
            # Für dieses Beispiel nehmen wir an, wir holen sie aus recurring_entries:
            cur.execute("""
                SELECT description, "usage"
                FROM recurring_entries
                WHERE id = %s AND user_id = %s
            """, (rec_id, user_id))
            rec_info = cur.fetchone()

            if rec_info:
                 desc, usage = rec_info
                 insert_params = (user_id, transaction_date.isoformat(), desc, usage, amount, rec_id)
                 # logging.debug(f"Inserting initial transaction for recurring_entry {rec_id} on {transaction_date.isoformat()}") # Zu detailliert für INFO
                 cur.execute(insert_query, insert_params)
                 # Optional: Logge die eingefügte Transaktion (nur wenn tatsächlich eingefügt)
                 # if cur.rowcount > 0:
                 #    logging.info(f"Inserted initial transaction for recurring_entry {rec_id} on {transaction_date.isoformat()}")
            else:
                 logging.error(f"Could not find recurring_entry {rec_id} for user {user_id} to create initial transactions.")
                 # Optional: Rollback oder Fehlerbehandlung, wenn recurring_entry nicht gefunden wird


        conn.commit()
        logging.info(f"Finished creating {duration} fix transactions for recurring_entry {rec_id}")

    except Exception as e:
        logging.exception(f"An error occurred in create_fix_transactions for recurring_entry {rec_id}:")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# Optional: Weitere Funktionen für Fixkosten könnten hier folgen
