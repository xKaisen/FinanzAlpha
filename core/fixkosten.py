from datetime import date
from core.db import get_db_connection

def insert_missing_fix_transactions(user_id: int, year: str, month: int):
    if year.lower() == "archiv":
        return

    conn = get_db_connection()
    cur = conn.cursor()

    # Alle Fixkosten
    cur.execute("""
        SELECT id, description, usage, amount, duration, start_date
        FROM recurring_entries
        WHERE user_id = ?
    """, (user_id,))
    fix_entries = cur.fetchall()

    # Bereits vorhandene Fixkosten
    cur.execute("""
        SELECT recurring_id, strftime('%Y', date), strftime('%m', date)
        FROM transactions
        WHERE user_id = ? AND recurring_id IS NOT NULL
    """, (user_id,))
    existing = {(int(r[0]), int(r[1]), int(r[2])) for r in cur.fetchall()}

    # Welche Monate prüfen?
    months_to_check = range(1, 13) if month == 0 else [month]

    inserts = []
    for rec_id, desc, usage, amount, duration, start_date in fix_entries:
        start_y, start_m, *_ = map(int, str(start_date).split("-"))
        for m in months_to_check:
            months_passed = (int(year) - start_y) * 12 + m - start_m
            if months_passed < 0 or months_passed >= duration:
                continue
            key = (rec_id, int(year), m)
            if key in existing:
                continue
            inserts.append((
                user_id,
                date(int(year), m, 1).isoformat(),
                desc, usage, float(amount), 0, rec_id
            ))

    if inserts:
        cur.executemany("""
            INSERT INTO transactions(user_id, date, description, "usage", amount, paid, recurring_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, inserts)
        conn.commit()

    conn.close()
