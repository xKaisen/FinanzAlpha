import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from core.db import get_db_connection, init_db
from core.auth import login_user, register_user
from core.version import __version__
from core.fixkosten import insert_missing_fix_transactions
from core.vorschlaege import bp as vorschlaege_bp
from datetime import date

def create_app():
    base = os.path.abspath(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base, 'web', 'templates'),
        static_folder=os.path.join(base, 'web', 'static')
    )
    app.secret_key = os.getenv("FLASK_SECRET", "a-very-secret-key")
    app.config.setdefault('DB_INITIALIZED', False)

    @app.before_request
    def ensure_db_initialized():
        if not app.config['DB_INITIALIZED']:
            init_db()
            app.config['DB_INITIALIZED'] = True

    @app.route('/')
    def index():
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            ok, res = login_user(username, password)
            if not ok:
                flash(res, 'error')
                return render_template('login.html', username=username, version=__version__)
            user_id, is_admin = res
            session.clear()
            session['user_id'] = user_id
            session['username'] = username
            session['is_admin'] = is_admin
            flash("Erfolgreich angemeldet!", 'success')
            return redirect(url_for('dashboard'))
        return render_template('login.html', version=__version__)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            is_admin = bool(request.form.get('is_admin'))
            ok, msg = register_user(username, password, is_admin)
            if not ok:
                flash(msg, 'error')
                return render_template('register.html', username=username, version=__version__)
            flash(msg, 'success')
            return redirect(url_for('login'))
        return render_template('register.html', version=__version__)

    @app.route('/logout')
    def logout():
        session.clear()
        flash("Abgemeldet.", 'info')
        return redirect(url_for('login'))

    @app.route('/dashboard')
    def dashboard():
        if not session.get('user_id'):
            return redirect(url_for('login'))

        user_id = session['user_id']
        today = date.today()
        year = request.args.get('year', str(today.year))
        month = request.args.get('month', str(today.month))
        q = request.args.get('q', '').strip()

        try:
            month_int = int(month) if month.isdigit() else 0
        except ValueError:
            month_int = 0

        # fehlende Fixkosten automatisch ergänzen
        insert_missing_fix_transactions(user_id, year, month_int)

        # Filterkriterien
        cond = ["user_id = ?"]
        params = [user_id]
        if year.lower() == 'archiv':
            cond.append("strftime('%Y', date) BETWEEN '2020' AND '2024'")
        else:
            cond.append("strftime('%Y', date) = ?")
            params.append(year)
        if month.isdigit() and 1 <= int(month) <= 12:
            cond.append("strftime('%m', date) = ?")
            params.append(f"{int(month):02d}")
        if q:
            cond.append("(lower(description) LIKE ? OR lower(\"usage\") LIKE ?)")
            like = f"%{q.lower()}%"
            params.extend([like, like])

        sql = f"""
            SELECT id, date, description, "usage", amount, paid, recurring_id
            FROM transactions
            WHERE {' AND '.join(cond)}
            ORDER BY date ASC
        """

        conn = get_db_connection()
        rows = conn.execute(sql, params).fetchall()
        saldo = sum(r['amount'] for r in rows)
        offen = sum(r['amount'] for r in rows if r['amount'] < 0 and not r['paid'] and r['recurring_id'])
        conn.close()

        return render_template(
            'dashboard_template.html',
            version=__version__,
            username=session.get('username'),
            year=year,
            month=month,
            current_year=str(today.year),
            transactions=rows,
            q=q,
            saldo=saldo,
            offen=offen
        )

    @app.route('/add_entry', methods=['POST'])
    def add_entry():
        if not session.get('user_id'):
            return redirect(url_for('login'))

        user_id = session['user_id']
        desc = request.form.get('description', '').strip()
        usage = request.form.get('usage', '').strip()
        amount_str = request.form.get('amount', '').replace(',', '.')
        duration = request.form.get('duration', '').strip()
        today_m1 = date.today().replace(day=1)

        try:
            amount = float(amount_str)
        except ValueError:
            flash("Ungültiger Betrag.", 'error')
            return redirect(url_for('dashboard'))

        if not desc or not usage:
            flash("Beschreibung und Verwendungszweck dürfen nicht leer sein.", 'error')
            return redirect(url_for('dashboard'))

        conn = get_db_connection()
        cur = conn.cursor()
        if duration.isdigit() and int(duration) > 1:
            cur.execute("""
                INSERT INTO recurring_entries
                (user_id, description, usage, amount, duration, start_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, desc, usage, amount, int(duration), today_m1))
            recurring_id = cur.lastrowid
            for i in range(int(duration)):
                y = today_m1.year + (today_m1.month + i - 1) // 12
                m = (today_m1.month + i - 1) % 12 + 1
                entry_date = date(y, m, 1).isoformat()
                cur.execute("""
                    INSERT INTO transactions
                    (user_id, date, description, "usage", amount, paid, recurring_id)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (user_id, entry_date, desc, usage, amount, recurring_id))
        else:
            cur.execute("""
                INSERT INTO transactions
                (user_id, date, description, "usage", amount, paid)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (user_id, today_m1.isoformat(), desc, usage, amount))
        conn.commit()
        conn.close()
        flash("Eintrag erfolgreich hinzugefügt.", 'success')
        return redirect(url_for('dashboard'))

    @app.route('/delete_entries', methods=['POST'])
    def delete_entries():
        if not session.get('user_id'):
            return redirect(url_for('login'))

        user_id = session['user_id']
        ids = request.form.getlist('delete_ids')
        if not ids:
            flash("Keine Einträge ausgewählt.", 'error')
            return redirect(url_for('dashboard'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.executemany(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            [(int(eid), user_id) for eid in ids]
        )
        conn.commit()
        conn.close()
        flash(f"{len(ids)} Eintrag(e) gelöscht.", 'success')
        return redirect(url_for('dashboard'))

    @app.route('/toggle_paid/<int:entry_id>', methods=['POST'])
    def toggle_paid(entry_id):
        if not session.get('user_id'):
            return redirect(url_for('login'))

        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()
        row = cur.execute("""
            SELECT paid, amount, recurring_id
            FROM transactions
            WHERE id = ? AND user_id = ?
        """, (entry_id, user_id)).fetchone()
        if row is None:
            conn.close()
            flash("Eintrag nicht gefunden.", 'error')
            return redirect(url_for('dashboard'))

        paid, amount, rec_id = row['paid'], row['amount'], row['recurring_id']
        # Nur negative Fixkosten toggeln
        if amount >= 0 or rec_id is None:
            conn.close()
            flash("Nur negative Fixkosten können umgeschaltet werden.", 'error')
            return redirect(url_for('dashboard'))

        new_status = 0 if paid else 1
        cur.execute(
            "UPDATE transactions SET paid = ? WHERE id = ? AND user_id = ?",
            (new_status, entry_id, user_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    @app.route('/fixkosten', methods=['GET', 'POST'])
    def fixkosten():
        if not session.get('user_id'):
            return redirect(url_for('login'))

        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()

        # Löschen ausgewählter Fixkosten
        if request.method == 'POST' and request.form.get('delete_fix'):
            ids = request.form.getlist('delete_id')
            if ids:
                cur.executemany(
                    "DELETE FROM recurring_entries WHERE id = ? AND user_id = ?",
                    [(int(i), user_id) for i in ids]
                )
                conn.commit()
                flash(f"{len(ids)} Fixkosten gelöscht.", 'success')
            else:
                flash("Keine Einträge ausgewählt.", 'error')

        # Hinzufügen neuer Fixkosten
        elif request.method == 'POST' and request.form.get('add_fix'):
            desc = request.form.get('description', '').strip()
            usage = request.form.get('usage', '').strip()
            amount = float(request.form.get('amount', '0').replace(',', '.'))
            duration = int(request.form.get('duration', '1'))
            start_date = request.form.get('start_date', date.today().isoformat())

            cur.execute("""
                INSERT INTO recurring_entries
                (user_id, description, usage, amount, duration, start_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, desc, usage, amount, duration, start_date))
            conn.commit()
            flash("Fixkosten hinzugefügt.", 'success')

        # Anzeige aller Fixkosten
        rows = cur.execute("""
            SELECT id, description, usage, amount, duration, start_date
            FROM recurring_entries
            WHERE user_id = ?
            ORDER BY start_date DESC
        """, (user_id,)).fetchall()
        conn.close()

        return render_template(
            'fixkosten_template.html',
            version=__version__,
            username=session.get('username'),
            fixes=rows,
            today=date.today().isoformat()
        )

    # Blueprint für Vorschläge registrieren
    app.register_blueprint(vorschlaege_bp)

    return app

if __name__ == '__main__':
    create_app().run(debug=True, port=5000)
