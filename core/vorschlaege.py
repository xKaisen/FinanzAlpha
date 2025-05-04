from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from core.db import get_db_connection
from core.version import __version__
from datetime import date

bp = Blueprint('vorschlaege', __name__, url_prefix='/vorschlaege')


@bp.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()

    # Automatisch Vorschläge aus Transaktionen ergänzen
    cur.execute("SELECT DISTINCT description FROM transactions WHERE user_id = ?", (user_id,))
    for (desc,) in cur.fetchall():
        if desc:
            cur.execute(
                "INSERT OR IGNORE INTO suggestions (user_id, suggestion_type, text) VALUES (?, 'description', ?)",
                (user_id, desc)
            )

    cur.execute("SELECT DISTINCT usage FROM transactions WHERE user_id = ?", (user_id,))
    for (usage,) in cur.fetchall():
        if usage:
            cur.execute(
                "INSERT OR IGNORE INTO suggestions (user_id, suggestion_type, text) VALUES (?, 'usage', ?)",
                (user_id, usage)
            )

    conn.commit()

    # === POST: Vorschläge löschen ===
    if request.method == 'POST' and request.form.get('delete_sugg'):
        selected_items = request.form.getlist('delete_item')  # z.B. ["description|Miete"]
        if selected_items:
            deleted = 0
            for item in selected_items:
                try:
                    typ, txt = item.split('|', 1)
                    cur.execute(
                        "DELETE FROM suggestions WHERE user_id = ? AND suggestion_type = ? AND text = ?",
                        (user_id, typ, txt)
                    )
                    deleted += 1
                except ValueError:
                    continue
            conn.commit()
            flash(f"{deleted} Vorschlag/Vorschläge gelöscht.", 'warning')
        else:
            flash("Keine Vorschläge ausgewählt.", 'error')
        return redirect(url_for('vorschlaege.index'))

    # === POST: Vorschlag hinzufügen ===
    if request.method == 'POST' and request.form.get('add_sugg'):
        typ = request.form.get('type', '').strip()
        txt = request.form.get('text', '').strip()

        if typ in ('description', 'usage') and txt:
            cur.execute(
                "INSERT OR IGNORE INTO suggestions (user_id, suggestion_type, text) VALUES (?, ?, ?)",
                (user_id, typ, txt)
            )
            conn.commit()
            flash("Vorschlag hinzugefügt.", 'success')
        else:
            flash("Ungültiger Vorschlag oder Kategorie.", 'error')
        return redirect(url_for('vorschlaege.index'))

    # === GET: Vorschläge anzeigen ===
    cur.execute("""
        SELECT suggestion_type, text
        FROM suggestions
        WHERE user_id = ?
        ORDER BY suggestion_type, text
    """, (user_id,))
    vorschlaege = cur.fetchall()
    conn.close()

    return render_template(
        'vorschlaege.html',  # <== Hier wird deine HTML-Datei geladen
        vorschlaege=vorschlaege,
        username=session.get('username'),
        version=__version__
    )
