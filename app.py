# app.py (Vollständig & Angepasst mit Changelog Route und Sync Route)
import os
import sys
# Projekt-Root am Anfang des Suchpfads (HACK, bis das Paket installiert ist)
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import logging
import markdown
from datetime import date
from sqlalchemy.engine import Engine

# Umgebungs­variablen laden (FLASK_SECRET, DB_URL usw.)
load_dotenv()

# Eigene Module
from core.db import get_db_connection, init_db
from core.auth import login_user, register_user
from core.version import __version__
from core.fixkosten import create_fix_transactions
from core.vorschlaege import bp as vorschlaege_bp
from api import api, sync_bp
from sync import sync               # <-- Import der lokalen Sync-Funktion

# ganz oben, nach Deinen Imports
from core.db import engine

def is_sqlite() -> bool:
    return engine.url.get_backend_name() == 'sqlite'


# --- Importiere Update-Funktionen ---
# Stelle sicher, dass es eine Datei 'updater.py' im selben Verzeichnis wie app.py gibt
# und diese die Funktionen check_for_update und install_update enthält.
# Wenn der Import fehlschlägt (z.B. Datei existiert nicht, Syntaxfehler), wird die Update-Funktionalität deaktiviert.
try:
    # check_for_update sollte die aktuelle Version (__version__) als Argument akzeptieren
    from updater import check_for_update, install_update
except ImportError:
    # Logge eine Warnung, wenn updater.py nicht gefunden wird (Datei fehlt, Name falsch, etc.)
    logging.warning("Could not import updater module (updater.py not found or has import errors). Update functionality will be disabled.", exc_info=True)
    check_for_update = None
    install_update = None
except Exception as e:
    logging.error(f"An unexpected error occurred during updater module import: {e}", exc_info=True)
    check_for_update = None
    install_update = None
# ------------------------------------

# --- Konfiguriere Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def create_app():
    base = os.path.abspath(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base, 'web', 'templates'),
        static_folder=os.path.join(base, 'web', 'static')
    )
    app.secret_key = os.getenv("FLASK_SECRET", "ein-sehr-geheimer-entwicklungs-schluessel-bitte-aendern")
    app.config.setdefault('DB_INITIALIZED', False)

    # --- Request Hook: Wird VOR jeder Anfrage ausgeführt ---
    @app.before_request
    def ensure_db_initialized():
        if not app.config['DB_INITIALIZED']:
            try:
                init_db()
                app.config['DB_INITIALIZED'] = True
                logging.info("Datenbank initialisiert.")
                logging.info(f"Aktuelle Version {__version__} als zuletzt gestartete Version gespeichert (Platzhalter).")
            except Exception as e:
                logging.error(f"Kritischer Fehler bei der Datenbankinitialisierung oder beim Speichern der Version: {e}", exc_info=True)
                app.config['DB_INITIALIZED'] = True
                flash("Fehler bei der Datenbankinitialisierung. Die App funktioniert möglicherweise nicht richtig.", 'error')

    # --- Context Processor: Wird VOR jedem Template-Rendering ausgeführt ---
    @app.context_processor
    def inject_update_flag():
        is_desktop = False
        latest_version = None
        update_available = False
        if hasattr(request, 'args'):
            is_desktop = request.args.get("desktop") == "1"
        if is_desktop and check_for_update:
            try:
                check_result = check_for_update(__version__)
                if isinstance(check_result, tuple) and len(check_result) > 0:
                    potential_latest_version = check_result[0]
                    if isinstance(potential_latest_version, str):
                        latest_version = potential_latest_version
                    elif potential_latest_version is not None:
                        logging.warning(f"check_for_update gab unerwarteten Typ für latest_version zurück: {type(potential_latest_version)}.")
            except Exception as e:
                logging.error(f"Fehler bei Update-Check für Template im context processor: {e}", exc_info=True)
        update_available = latest_version is not None
        return {
            'is_desktop': is_desktop,
            'latest_available_version': latest_version,
            'update_available': update_available,
            'app_version': __version__,
            'username': session.get('username'),
            'is_admin': session.get('is_admin', False)
        }
    # ------------------------------------

    # --- Routen Definitionen ---
    @app.route('/')
    def index():
        is_desktop_request = request.args.get("desktop") == "1"
        session['is_desktop_session'] = is_desktop_request
        logging.info(f"Root Request. Desktop status set in session: {is_desktop_request}")
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        if is_desktop_request:
            logging.info("Desktop-Parameter im Wurzel-Request gefunden, leite zu /login?desktop=1 weiter.")
            return redirect(url_for('login', desktop='1'))
        else:
            logging.info("Kein Desktop-Parameter im Wurzel-Request gefunden, leite zu /login weiter.")
            return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            ok, res = login_user(username, password)
            if not ok:
                flash(res, 'error')
                return render_template('login.html', username=username)
            user_id, is_admin = res
            old_is_desktop_session = session.get('is_desktop_session', False)
            session.clear()
            session['user_id'] = user_id
            session['username'] = username
            session['is_admin'] = is_admin
            session['is_desktop_session'] = old_is_desktop_session
            flash("Erfolgreich angemeldet!", 'success')
            return redirect(url_for('dashboard'))
        if request.method == 'GET':
            is_desktop_request = request.args.get("desktop") == "1"
            session['is_desktop_session'] = is_desktop_request
            logging.info(f"Login GET Request. Desktop status set in session: {is_desktop_request}")
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            is_admin = bool(request.form.get('is_admin'))
            ok, msg = register_user(username, password, is_admin)
            if not ok:
                flash(msg, 'error')
                return render_template('register.html', username=username)
            flash(msg, 'success')
            return redirect(url_for('login'))
        return render_template('register.html')

    @app.route('/logout')
    def logout():
        is_desktop_status = session.get('is_desktop_session', False)
        session.clear()
        flash("Abgemeldet.", 'info')
        logging.info(f"Benutzer abgemeldet. Desktop Status vor Session Clear genutzt: {is_desktop_status}")
        if is_desktop_status:
            return redirect(url_for('login', desktop='1'))
        else:
            return redirect(url_for('login'))

    @app.route('/changelog')
    def changelog():
        changelog_path = os.path.join(app.root_path, 'CHANGELOG.md')
        changelog_content = "Changelog Datei nicht gefunden."
        try:
            with open(changelog_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
                changelog_content = markdown.markdown(markdown_text)
        except FileNotFoundError:
            logging.error(f"CHANGELOG.md nicht gefunden unter {changelog_path}")
        except Exception as e:
            logging.error(f"Fehler beim Lesen oder Konvertieren von CHANGELOG.md: {e}", exc_info=True)
            changelog_content = f"Fehler beim Laden des Changelogs: {e}"
        return render_template('changelog.html', changelog_content=changelog_content)

    @app.route('/sync_data', methods=['POST'])
    def sync_data():
        if not session.get('user_id'):
            flash("Bitte melde dich an, um Daten zu synchronisieren.", 'warning')
            is_desktop_status = session.get('is_desktop_session', False)
            return redirect(url_for('login', desktop='1' if is_desktop_status else None))
        user_id = session['user_id']
        logging.info(f"Sync-Anforderung für Nutzer {user_id} erhalten.")
        # Hier erfolgt nun der tatsächliche Sync
        try:
            sync(user_id)
            flash("Synchronisierung erfolgreich.", 'success')
        except Exception as e:
            logging.error(f"Fehler beim Synchronisieren: {e}", exc_info=True)
            flash("Synchronisierung fehlgeschlagen.", 'error')
        is_desktop_status = session.get('is_desktop_session', False)
        return redirect(url_for('dashboard', desktop='1' if is_desktop_status else None))

    @app.route('/dashboard')
    def dashboard():
        # Prüfe, ob der Benutzer angemeldet ist
        if not session.get('user_id'):
            flash("Bitte melde dich an, um das Dashboard zu sehen.", 'warning')
            is_desktop = session.get('is_desktop_session', False)
            return redirect(url_for('login', desktop='1' if is_desktop else None))

        # Ab hier richtig eingerückt!
        user_id = session['user_id']
        today = date.today()
        year_str = request.args.get('year', str(today.year))
        month_str = request.args.get('month', str(today.month))
        q = request.args.get('q', '').strip()

        # Erkennen, ob wir SQLite oder Postgres nutzen
        sqlite_mode = is_sqlite()  # Deine Hilfsfunktion, z.B. aus core/db
        ph = "?" if sqlite_mode else "%s"
        year_expr = "CAST(strftime('%Y', date) AS INTEGER)" if sqlite_mode else "EXTRACT(YEAR FROM date)"
        month_expr = "CAST(strftime('%m', date) AS INTEGER)" if sqlite_mode else "EXTRACT(MONTH FROM date)"

        # WHERE‑Klausel zusammensetzen
        cond = [f"user_id = {ph}"]
        params = [user_id]

        if year_str.lower() == 'archiv':
            cond.append(f"{year_expr} BETWEEN 2020 AND {year_expr}")
        else:
            try:
                y = int(year_str)
                cond.append(f"{year_expr} = {ph}")
                params.append(y)
            except ValueError:
                logging.warning("Ungültiges Jahresformat, überspringe Jahresfilter")

        if year_str.lower() != 'archiv':
            try:
                m = int(month_str)
                if 1 <= m <= 12:
                    cond.append(f"{month_expr} = {ph}")
                    params.append(m)
            except ValueError:
                pass

        if q:
            cond.append(f"(LOWER(description) LIKE {ph} OR LOWER(\"usage\") LIKE {ph})")
            likeq = f"%{q.lower()}%"
            params += [likeq, likeq]

        sql = f"""
            SELECT id, date, description, "usage", amount, paid, recurring_id
              FROM transactions
             WHERE {' AND '.join(cond)}
             ORDER BY date, id
        """

        # Abfrage ausführen
        conn = None
        rows = []
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            logging.info(f"Dashboard: {len(rows)} Transaktionen gefunden.")
        except Exception as e:
            logging.error("Dashboard: Fehler beim Abrufen der Transaktionen:", exc_info=True)
            flash("Fehler beim Laden der Transaktionen.", 'error')
        finally:
            if conn:
                conn.close()

        # Zeilen verarbeiten
        transactions = []
        for r in rows:
            date_val = r[1]
            if isinstance(date_val, str):
                date_val = date.fromisoformat(date_val)
            transactions.append({
                'id': r[0],
                'date': date_val,
                'description': r[2],
                'usage': r[3],
                'amount': float(r[4]),
                'paid': bool(r[5]),
                'recurring_id': r[6],
            })

        # Saldo und offene Fixkosten berechnen
        saldo = sum(t['amount'] for t in transactions)
        offen = sum(
            -t['amount']
            for t in transactions
            if t['amount'] < 0 and not t['paid'] and t['recurring_id'] is not None
        )
        logging.info(f"Dashboard: Berechneter Saldo: {saldo}, Offene Fixkosten: {offen}")

        # Verfügbare Jahre und Monate ermitteln
        available_years = []
        available_months = []
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Jahre
            cur.execute(
                f"""
                SELECT DISTINCT {year_expr} AS year
                  FROM transactions
                 WHERE user_id = {ph}
                 ORDER BY year DESC
                """,
                (user_id,)
            )
            available_years = [int(r[0]) for r in cur.fetchall()]

            # Monate (sofern kein Archiv)
            if year_str.lower() != 'archiv':
                sel_year = int(year_str)
                cur.execute(
                    f"""
                    SELECT DISTINCT {month_expr} AS month
                      FROM transactions
                     WHERE user_id = {ph} AND {year_expr} = {ph}
                     ORDER BY month ASC
                    """,
                    (user_id, sel_year)
                )
                available_months = [int(r[0]) for r in cur.fetchall()]
        except Exception as e:
            logging.error("Dashboard: Fehler beim Abrufen verfügbarer Jahre/Monate:", exc_info=True)
        finally:
            if conn:
                conn.close()

        # Template rendern
        return render_template(
            'dashboard_template.html',
            username=session.get('username'),
            year=year_str,
            month=month_str,
            current_year=str(today.year),
            transactions=transactions,
            q=q,
            saldo=saldo,
            offen=offen,
            user_id=user_id,
            is_admin=session.get('is_admin', False),
            available_years=available_years,
            available_months=available_months
        )

    @app.route('/add_entry', methods=['POST'])
    def add_entry():
        if not session.get('user_id'):
            flash("Bitte melde dich an.", 'warning')
            is_desktop_status = session.get('is_desktop_session', False)
            if is_desktop_status:
                 return redirect(url_for('login', desktop='1'))
            else:
                 return redirect(url_for('login'))

        user_id = session['user_id']
        desc = request.form.get('description', '').strip()
        usage = request.form.get('usage', '').strip()
        amount_raw = request.form.get('amount', '').replace(',', '.').strip()
        # duration_str wurde aus dem Formular entfernt, ist aber noch in der Logik relevant
        # Hier müsstest du entscheiden, wie wiederkehrende Einträge hinzugefügt werden.
        # Wenn sie nur über "Fixkosten" hinzugefügt werden, kann duration hier weg.
        # Wenn add_entry auch einmalige + wiederkehrende handhabt, brauche es duration ODER eine andere Unterscheidung.
        # Lassen wir duration hier erstmal weg, da es im HTML entfernt wurde
        # duration_str = request.form.get('duration', '').strip() # Removed from HTML

        entry_date_str = request.form.get('entry_date', date.today().isoformat()) # Datum aus Formular, oder heute

        if not desc or not usage or not amount_raw:
             flash("Beschreibung, Verwendungszweck und Betrag sind erforderlich.", 'error')
             return redirect(url_for('dashboard'))

        try:
            amount = float(amount_raw)
        except ValueError:
            flash("Ungültiger Betrag eingegeben.", 'error')
            return redirect(url_for('dashboard'))

        conn = None
        try:
            conn = get_db_connection() # Verwendet die angepasste Funktion
            cur = conn.cursor()

            # Bestimme den Datenbanktyp und den passenden Platzhalter
            db_type = os.getenv("DATABASE_TYPE", "postgresql").lower()
            placeholder = "%s" if db_type == "postgresql" else "?"

            # Annahme: add_entry fügt nur einmalige Einträge hinzu (kein duration Feld mehr im HTML)
            # Füge einmalige Transaktion in transactions Tabelle ein
            # Einmalige Buchungen sind standardmäßig bezahlt (paid=TRUE), haben keine recurring_id
            sql = f"""
                INSERT INTO transactions
                  (user_id, date, description, "usage", amount, paid, recurring_id)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """
            # SQLite benötigt 0 für FALSE und 1 für TRUE
            paid_value = True if db_type == "postgresql" else 1

            # Datum als ISO-String speichern (funktioniert in beiden gut)
            try:
                entry_date = date.fromisoformat(entry_date_str)
            except ValueError:
                flash("Ungültiges Datumsformat.", 'error')
                return redirect(url_for('dashboard'))


            cur.execute(sql, (user_id, entry_date.isoformat(), desc, usage, amount, paid_value, None))
            conn.commit()
            flash("Einmaliger Eintrag erfolgreich hinzugefügt.", 'success')


        except Exception as e:
             logging.error(f"AddEntry: Fehler beim Hinzufügen des Eintrags für Nutzer {user_id}:", exc_info=True)
             if conn:
                conn.rollback()
             flash("Fehler beim Hinzufügen des Eintrags.", 'error')

        finally:
            if conn:
                conn.close()

        return redirect(url_for('dashboard'))


    @app.route('/delete_entries', methods=['POST'])
    def delete_entries():
        if not session.get('user_id'):
            flash("Bitte melde dich an.", 'warning')
            is_desktop_status = session.get('is_desktop_session', False)
            if is_desktop_status:
                 return redirect(url_for('login', desktop='1'))
            else:
                 return redirect(url_for('login'))

        user_id = session['user_id']
        ids_to_delete_str = request.form.getlist('delete_ids')

        if not ids_to_delete_str:
            flash("Keine Einträge zum Löschen ausgewählt.", 'error')
            return redirect(url_for('dashboard'))

        valid_ids = []
        for entry_id_str in ids_to_delete_str:
            try:
                valid_ids.append(int(entry_id_str))
            except ValueError:
                logging.warning(f"DeleteEntries: Ungültige ID '{entry_id_str}' in Anfrage erhalten.")

        if not valid_ids:
             flash("Keine gültigen Einträge zum Löschen ausgewählt.", 'error')
             return redirect(url_for('dashboard'))

        logging.info(f"DeleteEntries: Nutzer {user_id} versucht, Transaktionen mit IDs {valid_ids} zu löschen.")

        conn = None
        deleted_count = 0
        try:
            conn = get_db_connection() # Verwendet die angepasste Funktion
            cur = conn.cursor()

            # Bestimme den Datenbanktyp und den passenden Platzhalter
            db_type = os.getenv("DATABASE_TYPE", "postgresql").lower()
            placeholder = "%s" if db_type == "postgresql" else "?"

            # Lösche die Transaktionen. Verwende IN Clause sicher.
            # SQL-Abfrage verwendet IN Clause sicher
            # Erstelle einen String wie "id IN (%s, %s, ...)" oder "id IN (?, ?, ...)"
            id_placeholders = ', '.join([placeholder] * len(valid_ids))
            sql = f"DELETE FROM transactions WHERE id IN ({id_placeholders}) AND user_id = {placeholder}"
            delete_params = valid_ids + [user_id] # Parameterliste zusammenfügen

            cur.execute(sql, delete_params)
            deleted_count = cur.rowcount
            conn.commit()

            logging.info(f"DeleteEntries: Erfolgreich {deleted_count} Transaktion(en) für Nutzer {user_id} gelöscht.")
            flash(f"{deleted_count} Eintrag(e) erfolgreich gelöscht.", 'success')

        except Exception as e:
            logging.error(f"DeleteEntries: Fehler beim Löschen der Einträge für Nutzer {user_id}:", exc_info=True)
            if conn:
                conn.rollback()
            flash("Fehler beim Löschen der Einträge.", 'error')

        finally:
            if conn:
                conn.close()

        return redirect(url_for('dashboard'))


    @app.route('/fixkosten', methods=['GET', 'POST'])
    def fixkosten():
        if not session.get('user_id'):
            flash("Bitte melde dich an, um Fixkosten zu verwalten.", 'warning')
            is_desktop_status = session.get('is_desktop_session', False)
            if is_desktop_status:
                 return redirect(url_for('login', desktop='1'))
            else:
                 return redirect(url_for('login'))

        user_id = session['user_id']
        conn = None

        # Bestimme den Datenbanktyp und den passenden Platzhalter für diese Route
        db_type = os.getenv("DATABASE_TYPE", "postgresql").lower()
        placeholder = "%s" if db_type == "postgresql" else "?"

        if request.method == 'POST':
             conn = get_db_connection() # Verwendet die angepasste Funktion
             cur = conn.cursor()
             try:
                if request.form.get('add_fix'):
                    desc = request.form.get('description', '').strip()
                    usage = request.form.get('usage', '').strip()
                    amount_raw = request.form.get('amount', '0').replace(',', '.').strip()
                    duration_str = request.form.get('duration', '').strip()
                    start_iso = request.form.get('start_date', date.today().isoformat())

                    if not desc or not usage or not amount_raw or not duration_str or not start_iso:
                         flash("Alle Fixkosten-Felder sind erforderlich.", 'error')
                    else:
                        try:
                            amount = float(amount_raw)
                            dur = int(duration_str)
                            sd = date.fromisoformat(start_iso).replace(day=1)
                        except ValueError:
                            flash("Ungültige Fixkosten-Daten (Betrag, Dauer oder Startdatum).", 'error')
                        else:
                            if not (1 <= dur <= 12):
                                flash("Dauer muss zwischen 1 und 12 Monaten liegen.", 'error')
                            else:
                                logging.info(f"Fixkosten: Füge neuen wiederkehrenden Eintrag für Nutzer {user_id} hinzu.")
                                try:
                                    # Bestimme den Platzhalter für die recurring_entries Tabelle
                                    rec_entry_placeholder = "%s" if db_type == "postgresql" else "?"

                                    # 1) recurring_entries anlegen
                                    sql_rec = f"""
                                        INSERT INTO recurring_entries
                                          (user_id, description, "usage", amount, duration, start_date)
                                        VALUES ({rec_entry_placeholder}, {rec_entry_placeholder}, {rec_entry_placeholder}, {rec_entry_placeholder}, {rec_entry_placeholder}, {rec_entry_placeholder})
                                        RETURNING id
                                    """
                                    cur.execute(sql_rec, (user_id, desc, usage, amount, dur, sd.isoformat()))
                                    rec_id = cur.fetchone()[0]
                                    conn.commit()

                                    # 2) Monats-Transaktionen erzeugen
                                    # create_fix_transactions muss die richtige DB-Verbindung über get_db_connection nutzen
                                    # und mit dem passenden Platzhalter arbeiten können!
                                    create_fix_transactions(user_id, rec_id, sd, amount, dur)
                                    conn.commit()
                                    flash(f"Fixkosten ({dur} Monate) angelegt und zugehörige Transaktionen erstellt.", 'success')

                                except Exception as e:
                                     logging.error(f"Fixkosten: Fehler beim Hinzufügen der Fixkosten für Nutzer {user_id}:", exc_info=True)
                                     conn.rollback()
                                     flash("Fehler beim Hinzufügen der Fixkosten.", 'error')


                elif request.form.get('delete_fix'):
                    ids_to_delete_str = request.form.getlist('delete_id')
                    if not ids_to_delete_str:
                        flash("Keine Fixkosten zum Löschen ausgewählt.", 'error')
                    else:
                        valid_ids = []
                        for fix_id_str in ids_to_delete_str:
                            try:
                                valid_ids.append(int(fix_id_str))
                            except ValueError:
                                logging.warning(f"Fixkosten löschen: Ungültige ID '{fix_id_str}' in Anfrage erhalten.")

                        if valid_ids:
                            logging.info(f"Fixkosten: Nutzer {user_id} versucht, Fixkosten mit IDs {valid_ids} zu löschen.")
                            try:
                                # Lösche die wiederkehrenden Einträge.
                                rec_id_placeholders = ', '.join([placeholder] * len(valid_ids))
                                sql_del_rec = f"DELETE FROM recurring_entries WHERE id IN ({rec_id_placeholders}) AND user_id = {placeholder}"
                                delete_params = valid_ids + [user_id]

                                cur.execute(sql_del_rec, delete_params)
                                deleted_count = cur.rowcount
                                conn.commit()

                                logging.info(f"Fixkosten: Erfolgreich {deleted_count} wiederkehrende Einträge für Nutzer {user_id} gelöscht.")
                                flash(f"{deleted_count} Fixkosten erfolgreich gelöscht.", 'success')

                            except Exception as e:
                                logging.error(f"Fixkosten: Fehler beim Löschen der wiederkehrenden Einträge für Nutzer {user_id}:", exc_info=True)
                                conn.rollback()
                                flash("Fehler beim Löschen der Fixkosten.", 'error')
                        else:
                            flash("Keine gültigen Fixkosten zum Löschen ausgewählt.", 'error')
             except Exception as e:
                  logging.error("Unerwarteter Fehler in Fixkosten POST-Handling:", exc_info=True)
                  if conn: conn.rollback()
                  flash("Ein unerwarteter Fehler ist aufgetreten.", 'error')

             finally:
                  if conn:
                     conn.close()


        # Handle GET request (oder nach POST, um die aktualisierte Liste anzuzeigen)
        conn = None # Neue Verbindung für GET oder nach POST
        rows = []
        try:
            conn = get_db_connection() # Verwendet die angepasste Funktion
            cur = conn.cursor()
            # Hole alle wiederkehrenden Einträge für den angemeldeten Benutzer
            sql_select = f"""
                SELECT id, description, "usage", amount, duration, start_date
                  FROM recurring_entries
                 WHERE user_id = {placeholder}
                 ORDER BY start_date DESC, id DESC
            """
            cur.execute(sql_select, (user_id,))
            rows = cur.fetchall()
            logging.info(f"Fixkosten: {len(rows)} wiederkehrende Einträge für Nutzer {user_id} gefunden.")

        except Exception as e:
             logging.error(f"Fixkosten: Fehler beim Abrufen der wiederkehrenden Einträge für Nutzer {user_id}:", exc_info=True)
             rows = []
             flash("Fehler beim Laden der Fixkosten.", 'error')

        finally:
             if conn:
                conn.close()

        fixes = []
        try:
            fixes = [
                {
                    'id': r[0],
                    'description': r[1],
                    'usage': r[2],
                    'amount': float(r[3]),
                    'duration': r[4],
                    'start_date': date.fromisoformat(r[5]) if isinstance(r[5], str) else r[5], # Datum bei Bedarf konvertieren
                }
                for r in rows
            ]
        except Exception as e:
             logging.error("Fixkosten: Fehler beim Verarbeiten der Fixkosten-Ergebnisse:", exc_info=True)
             fixes = []


        return render_template(
            'fixkosten_template.html',
            username=session.get('username'),
            fixes=fixes,
            today=date.today().isoformat(),
            is_admin=session.get('is_admin', False)
        )


    @app.route('/api/transaction/<int:transaction_id>/toggle_paid', methods=['POST'])
    def toggle_paid_api(transaction_id):
        # Prüfe, ob Benutzer angemeldet ist
        if not session.get('user_id'):
            # Rückgabe einer JSON-Fehlermeldung für API-Aufrufe
            return jsonify({'success': False, 'error': 'Nicht authentifiziert.'}), 401

        user_id = session['user_id']
        data = request.get_json()
        new_paid_status = data.get('paid') # Erwartet 0 oder 1

        if new_paid_status is None or new_paid_status not in [0, 1]:
             return jsonify({'success': False, 'error': 'Ungültiger Paid-Status gesendet.'}), 400

        conn = None
        try:
            conn = get_db_connection() # Verwendet die angepasste Funktion
            cur = conn.cursor()

            # Bestimme den Datenbanktyp und den passenden Platzhalter
            db_type = os.getenv("DATABASE_TYPE", "postgresql").lower()
            placeholder = "%s" if db_type == "postgresql" else "?"

            # Führe das Update durch. Stelle sicher, dass nur der eigene Eintrag aktualisiert wird.
            # SQLite nutzt 0/1 für BOOLEAN
            paid_value_in_db = True if new_paid_status == 1 else False

            sql = f"""
                UPDATE transactions
                SET paid = {placeholder}
                WHERE id = {placeholder} AND user_id = {placeholder} AND recurring_id IS NOT NULL AND amount < 0
            """
            cur.execute(sql, (paid_value_in_db, transaction_id, user_id))

            if cur.rowcount == 0:
                 # Wenn keine Zeile aktualisiert wurde, bedeutet das, dass der Eintrag nicht existiert,
                 # nicht dem Benutzer gehört, keine Fixkosten ist oder nicht negativ ist.
                 conn.rollback() # Nichts zu committen, aber Rollback ist gute Praxis
                 logging.warning(f"TogglePaid: Update nicht durchgeführt für trans_id {transaction_id}, user_id {user_id}. Kriterien nicht erfüllt oder nicht gefunden.")
                 return jsonify({'success': False, 'error': 'Eintrag nicht gefunden oder nicht aktualisierbar.'}), 404

            conn.commit()
            logging.info(f"TogglePaid: Status für transaction {transaction_id} auf {new_paid_status} gesetzt durch user {user_id}.")
            return jsonify({'success': True, 'message': 'Status erfolgreich aktualisiert.'}), 200

        except Exception as e:
            logging.error(f"TogglePaid: Fehler beim Aktualisieren von transaction {transaction_id} durch user {user_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': 'Interner Serverfehler beim Aktualisieren.'}), 500

        finally:
            if conn:
                conn.close()


    # --- Update-Route (Angepasst für Desktop-Nutzer OHNE Login/Admin Check) ---
    @app.route('/start_update', methods=['POST'])
    def start_update():
        # KEINE Prüfung auf session.get('user_id') oder session.get('is_admin') mehr
        # Gemäß Anforderung kann JEDER Desktop-Nutzer das Update starten, auch auf der Login-Seite.

        # Sicherheitsprüfung: Stelle sicher, dass die Anfrage von einer Desktop-Instanz kommt.
        # Dies verhindert, dass beliebige Webbrowser das Update triggern.
        # Nutze den Wert aus der Session, der beim Betreten/Login gesetzt wurde
        is_desktop_status = session.get('is_desktop_session', False)
        if not is_desktop_status:
            flash("Update kann nur von der Desktop-Anwendung gestartet werden.", 'error')
            logging.warning("Update-Versuch von Nicht-Desktop erkannt.")
            # Leite zurück zur Login-Seite oder woher der Request kam
            # Nutze den Desktop-Status aus der Session, falls vorhanden (sollte ja False sein hier)
            if session.get('is_desktop_session', False): # Check ist redundant, da if not... true war
                 return redirect(url_for('login', desktop='1'))
            else:
                 return redirect(url_for('login'))


        # Prüfe, ob die Update-Funktionen verfügbar sind (Import erfolgreich)
        if check_for_update is None or install_update is None:
             flash("Update-Funktionalität nicht verfügbar (updater.py fehlt oder hat Fehler).", 'error')
             logging.error("Update-Funktionen (in updater.py?) nicht gefunden oder importiert.")
             # Leite zurück zur Login-Seite, mit dem Desktop-Parameter aus der Session
             if session.get('is_desktop_session', False):
                  return redirect(url_for('login', desktop='1'))
             else:
                  return redirect(url_for('login'))


        logging.info(f"Update-Prüfung/Start angefordert (Desktop).")

        try:
            # Rufe die check_for_update Funktion auf, um den neuesten Status und Download-Daten zu erhalten.
            # Übergebe die aktuelle Version (__version__). check_for_update MUSS dieses Argument akzeptieren.
            # Die check_for_update Funktion sollte intern Caching nutzen.
            update_available_from_check, update_data = check_for_update(__version__) # <-- Übergebe __version__

            # Stelle sicher, dass check_for_update True zurückgab UND Daten lieferte
            if update_available_from_check and update_data:
                flash(f"Update gefunden ({update_data.get('version', 'unbekannt')})! Die Anwendung wird neu gestartet, um das Update zu installieren.", 'info')
                logging.info(f"Update gefunden. Starte Installation mit Daten: {update_data}")

                # Rufe install_update auf. Diese Funktion ist dafür verantwortlich, den Prozess zu beenden!
                # Der folgende redirect wird vom ALTEN Prozess wahrscheinlich NICHT erreicht.
                install_update(update_data)

                # Fallback-Redirect, falls install_update den Prozess nicht beendet.
                # Leite zur Login-Seite um, mit dem Desktop-Parameter, falls es eine Desktop-Session war
                if session.get('is_desktop_session', False):
                     return redirect(url_for('login', desktop='1'))
                else:
                     return redirect(url_for('login'))

            else:
                # Dieser Fall wird erreicht, wenn check_for_update False oder (None, None) zurückgab.
                flash("Kein Update verfügbar oder Fehler beim Abrufen der Updatedaten.", 'info')
                logging.info("Update-Check von Route gestartet, aber kein Update gefunden oder Daten fehlen.")
                # Leite zurück zur Login-Seite, mit dem Desktop-Parameter, falls es eine Desktop-Session war
                if session.get('is_desktop_session', False):
                     return redirect(url_for('login', desktop='1'))
                else:
                     return redirect(url_for('login'))

        except Exception as e:
             # Fange alle unerwarteten Fehler während des Update-Prozesses ab (innerhalb der Route, vor install_update).
             logging.error("Fehler beim Starten des Updates:", exc_info=True)
             flash(f"Fehler beim Update-Prozess: {e}", 'error')
             # Leite zurück zur Login-Seite, mit dem Desktop-Parameter, falls es eine Desktop-Session war
             if session.get('is_desktop_session', False):
                  return redirect(url_for('login', desktop='1'))
             else:
                  return redirect(url_for('login'))

    # --- Blueprint Registrierungen ---
    # --- RESTX API und Blueprints registrieren ---
    # --- RESTX API und Blueprints registrieren ---
    # 1) binde flask_restx.Api an die App
    api.init_app(app)

    # 2) registriere Deine Blueprints
    app.register_blueprint(vorschlaege_bp)  # Vorschläge unter /<prefix>
    app.register_blueprint(sync_bp)         # Sync-API unter /api/sync

    return app


if __name__ == '__main__':
    app = create_app()
    try:
        from core.version import __version__ as app_version_for_log
        logging.info(f"Starte Flask-App Version {app_version_for_log}")
    except ImportError:
        logging.warning("Konnte core.version nicht importieren für Startmeldung.")
    logging.info("Starte Flask im reinen Web-Modus (direkt via app.py).")
    app.run(debug=False, port=5000, use_reloader=False, host='127.0.0.1')
