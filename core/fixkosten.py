from core.db import get_db_connection
from datetime import date

def insert_missing_fix_transactions(user_id, year, month):
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch all recurring entries for the user
    cur.execute("""
        SELECT id, description, usage, amount, duration, start_date
        FROM recurring_entries
        WHERE user_id = %s
    """, (user_id,))
    recurring_entries = cur.fetchall()

    for entry in recurring_entries:
        entry_id, description, usage, amount, duration, start_date = entry
        start_year = start_date.year
        start_month = start_date.month

        # Archiv-Zeitraum: 2020–2024
        if year == 'archiv':
            for y in range(2020, 2025):
                for m in range(1, 13):
                    if start_year < y or (start_year == y and start_month <= m):
                        entry_date = date(y, m, 1).isoformat()
                        cur.execute("""
                            INSERT INTO transactions
                              (user_id, date, description, usage, amount, paid, recurring_id)
                            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                            ON CONFLICT (user_id, recurring_id, date) DO NOTHING
                        """, (user_id, entry_date, description, usage, amount, entry_id))

        # Aktueller Monat im Dashboard
        else:
            year_int = int(year)
            month_int = int(month)
            if start_year < year_int or (start_year == year_int and start_month <= month_int):
                entry_date = date(year_int, month_int, 1).isoformat()
                cur.execute("""
                    INSERT INTO transactions
                      (user_id, date, description, usage, amount, paid, recurring_id)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (user_id, recurring_id, date) DO NOTHING
                """, (user_id, entry_date, description, usage, amount, entry_id))

    conn.commit()
    conn.close()
