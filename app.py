# app.py (Vollständig & Angepasst mit Changelog Route und Sync Route)
import os
import sys # Importiere sys für die Pfad-Ermittlung im AppData Helper
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei (z.B. FLASK_SECRET, DB_URL)
# Stelle sicher, dass eine .env Datei existiert, auch wenn nur mit FLASK_SECRET.
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
# Importiere deine Kernmodule
# Stelle sicher, dass diese Dateien und die benötigten Funktionen/Blueprints existieren.
# >>> PASSE DEN IMPORT AN: get_db_connection und init_db aus core.db holen <<<
from core.db import get_db_connection, init_db
from core.auth import login_user, register_user # Wird in /login und /register verwendet
from core.version import __version__, VersionService # __version__ für Versionsinfo, VersionService für last_version (optional genutzt)
from core.fixkosten import create_fix_transactions, insert_missing_fix_transactions # Wird in /add_entry und /fixkosten verwendet
from core.vorschlaege import bp as vorschlaege_bp # Dein Blueprint für Vorschläge
from api.routes import api as api_bp # Dein API Blueprint

from datetime import date
import logging # Importiere Logging
import markdown # <-- Füge den markdown Import hinzu! (Benötigt 'pip install markdown')


# --- Importiere Update-Funktionen ---
# Stelle sicher, dass es eine Datei 'updater.py' im selben Verzeichnis wie app.py gibt
# und diese die Funktionen check_for_update und install_update enthält.
# Wenn der Import fehlschlägt (z.B. Datei existiert nicht, Syntaxfehler), wird die Update-Funktionalität deaktiviert.
try:
    # check_for_update sollte die aktuelle Version (__version__) als Argument akzeptieren
    from updater import check_for_update, install_update
except ImportError:
    # Logge eine Warnung, wenn updater.py nicht gefunden wird (Datei fehlt, Name falsch, etc.)
    logging.warning("Could not import updater module (updater.py not found or has import errors). Update functionality will be disabled.", exc_info=True) # Logge exc_info
    check_for_update = None # Setze Funktionen auf None, wenn Import fehlschlägt
    install_update = None
except Exception as e:
     # Fange andere potenzielle Fehler beim Import ab (z.B. SyntaxError in updater.py)
     logging.error(f"An unexpected error occurred during updater module import: {e}", exc_info=True) # Logge den spezifischen Fehler
     check_for_update = None
     install_update = None
# ------------------------------------


# --- Konfiguriere Logging ---
# Setze das Level auf INFO, um auch Infos und Warnungen von Flask und deinen Modulen zu sehen
# Passe das Format ggf. an
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__) # Optional: eigenen Logger für app.py


def create_app():
    # Bestimme das Basisverzeichnis der Anwendung (dort, wo app.py liegt)
    base = os.path.abspath(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base, 'web', 'templates'), # Pfad zu deinen HTML-Templates
        static_folder=os.path.join(base, 'web', 'static')     # Pfad zu deinen statischen Dateien (CSS, JS, Bilder)
    )
    # Setze den geheimen Schlüssel aus Umgebungsvariablen (wichtig für Sessions)
    # Ändere den Standardwert in der Produktion!
    app.secret_key = os.getenv("FLASK_SECRET", "ein-sehr-geheimer-entwicklungs-schluessel-bitte-aendern")
    # Konfigurationsflag, um sicherzustellen, dass die DB nur einmal initialisiert wird
    app.config.setdefault('DB_INITIALIZED', False)

    # --- Request Hook: Wird VOR jeder Anfrage ausgeführt ---
    @app.before_request
    def ensure_db_initialized():
        # Initialisiere die Datenbank nur beim ersten Request
        if not app.config['DB_INITIALIZED']:
            try:
                init_db() # Rufe deine Datenbank-Initialisierungsfunktion auf
                app.config['DB_INITIALIZED'] = True
                logging.info("Datenbank initialisiert.")
                # Optional: Speichere die aktuelle Version nach erfolgreicher DB-Initialisierung
                # (Das signalisiert einen erfolgreichen Start bis zu diesem Punkt)
                # >>> Stelle sicher, dass VersionService die korrekte DB-Verbindung über get_db_connection nutzt <<<
                # VersionService.set_last_version(__version__) # Dies muss angepasst werden
                logging.info(f"Aktuelle Version {__version__} als zuletzt gestartete Version gespeichert (Platzhalter).") # Angepasste Meldung
            except Exception as e:
                logging.error(f"Kritischer Fehler bei der Datenbankinitialisierung oder beim Speichern der Version: {e}", exc_info=True)
                app.config['DB_INITIALIZED'] = True # Setze Flag, auch wenn Fehler, um Schleife zu vermeiden
                flash("Fehler bei der Datenbankinitialisierung. Die App funktioniert möglicherweise nicht richtig.", 'error')


    # --- Context Processor: Wird VOR jedem Template-Rendering ausgeführt ---
    @app.context_processor
    def inject_update_flag():
        """
        Stellt 'is_desktop', 'latest_available_version', 'update_available'
        und 'app_version' allen Templates zur Verfügung.
        Wird für das Update-Banner auf der Login-Seite und potenziell anderswo verwendet.
        """
        # Standardwerte
        is_desktop = False
        latest_version = None
        update_available = False

        # Bestimme, ob es sich um eine Desktop-Anwendung handelt, basierend auf dem Query-Parameter
        # request ist nur innerhalb eines Request-Kontextes verfügbar, muss geprüft werden
        if hasattr(request, 'args'):
             is_desktop = request.args.get("desktop") == "1"

        # Prüfe auf Updates nur, wenn es sich um eine Desktop-Anwendung handelt könnte
        # UND die check_for_update Funktion erfolgreich importiert wurde
        if is_desktop and check_for_update:
            try:
                # Rufe die check_for_update Funktion aus updater.py auf.
                # Übergebe die aktuelle Version (__version__) zur Vergleichung.
                # Erwartet zurück: (neueste_versionsnummer_string ODER None, Daten ODER None)
                # Die check_for_update Funktion sollte intern Caching nutzen, um nicht bei jeder Anfrage GitHub zu pollen.
                check_result = check_for_update(__version__) # <-- Übergebe __version__

                # Überprüfe das Ergebnis von check_for_update
                if isinstance(check_result, tuple) and len(check_result) > 0:
                     potential_latest_version = check_result[0]
                     # Setze latest_version nur, wenn es ein String ist (kann None sein)
                     if isinstance(potential_latest_version, str):
                          latest_version = potential_latest_version
                     elif potential_latest_version is not None:
                          logging.warning(f"check_for_update gab unerwarteten Typ für latest_version zurück: {type(potential_latest_version)}. Erwartet: str oder None.")


            except Exception as e:
                logging.error(f"Fehler bei Update-Check für Template im context processor: {e}", exc_info=True)
                # latest_version bleibt None im Fehlerfall

        # update_available ist True, wenn eine neuere Version gefunden wurde (latest_version ist ein String)
        update_available = latest_version is not None

        # Gib die Variablen für das Template zurück
        return {
            'is_desktop': is_desktop,                       # True, wenn ?desktop=1 in der URL
            'latest_available_version': latest_version,     # Die Versionsnummer des Updates (String) oder None
            'update_available': update_available,           # True, wenn ein Update gefunden wurde (latest_version ist nicht None)
            'app_version': __version__,                     # Die Version der aktuell laufenden App (aus core.version.py)
            'username': session.get('username'),            # Username (verfügbar, wenn angemeldet)
            'is_admin': session.get('is_admin', False)      # Admin Status (verfügbar, wenn angemeldet)
            # Weitere global benötigte Variablen können hier hinzugefügt werden
            # >>> Füge hier ggf. weitere Kontext-Variablen hinzu (z.B. fuer Dark Mode) <<<
        }
    # -----------------------------------------------------------------------


    # --- Routen Definitionen ---

    @app.route('/')
    def index():
        is_desktop_request = request.args.get("desktop") == "1"
        # Speichere den Desktop-Status in der Session für spätere Verwendung (z.B. Logout)
        session['is_desktop_session'] = is_desktop_request
        logging.info(f"Root Request. Desktop status set in session: {is_desktop_request}")

        if session.get('user_id'):
            # Wenn angemeldet, leite zum Dashboard weiter.
            return redirect(url_for('dashboard'))

        # Wenn nicht angemeldet, leite zur Login-Seite weiter.
        if is_desktop_request:
            logging.info("Desktop-Parameter im Wurzel-Request gefunden, leite zu /login?desktop=1 weiter.")
            return redirect(url_for('login', desktop='1')) # Pass the parameter
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
            logging.info("Umleitung zu /login?desktop=1 nach Abmeldung.")
            return redirect(url_for('login', desktop='1'))
        else:
            logging.info("Umleitung zu /login nach Abmeldung.")
            return redirect(url_for('login'))


    @app.route('/changelog')
    def changelog():
        """Route zur Anzeige des Anwendungs-Changelogs."""
        changelog_path = os.path.join(app.root_path, 'CHANGELOG.md')
        changelog_content = "Changelog Datei nicht gefunden." # Fallback-Nachricht

        try:
            with open(changelog_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
                changelog_content = markdown.markdown(markdown_text)
        except FileNotFoundError:
            logging.error(f"CHANGELOG.md nicht gefunden unter {changelog_path}")
            logging.debug(f"App Wurzelverzeichnis: {app.root_path}")
        except Exception as e:
            logging.error(f"Fehler beim Lesen oder Konvertieren von CHANGELOG.md: {e}", exc_info=True)
            changelog_content = f"Fehler beim Laden des Changelogs: {e}"

        return render_template('changelog.html', changelog_content=changelog_content)


    # --- NEUE ROUTE FÜR DATEN SYNCHRONISIERUNG (PLATZHALTER) ---
    # Diese Route wird vom Sync-Button im Dashboard aufgerufen
    @app.route('/sync_data', methods=['POST'])
    def sync_data():
        # Prüfe, ob Benutzer angemeldet ist
        if not session.get('user_id'):
            flash("Bitte melde dich an, um Daten zu synchronisieren.", 'warning')
            # Leite zur Login-Seite um, mit dem Desktop-Parameter, falls es eine Desktop-Session war
            is_desktop_status = session.get('is_desktop_session', False)
            if is_desktop_status:
                 return redirect(url_for('login', desktop='1'))
            else:
                 return redirect(url_for('login'))

        user_id = session['user_id']
        logging.info(f"Sync-Anforderung für Nutzer {user_id} erhalten.")

        # >>>>> HIER KOMMT SPÄTER DIE SYNCHRONISIERUNGSLOGIK HIN <<<<<
        # Lese den Desktop-Status aus der Session, um zu wissen, welche DB lokal ist
        is_desktop_session = session.get('is_desktop_session', False)
        if is_desktop_session:
             logging.info("Sync-Anforderung kommt von der Desktop-App (SQLite erwartet).")
             # Hier kommt die Logik, um Daten vom Server (PostgreSQL) abzurufen
             # und in die lokale SQLite-Datenbank zu schreiben.
        else:
             logging.info("Sync-Anforderung kommt von der Web-App (PostgreSQL erwartet).")
             # Hier käme Logik, um Daten vom Desktop (SQLite) abzurufen (falls Desktop-zu-Web-Sync gewünscht)
             # oder einfach eine Info, dass der Sync hauptsächlich für Desktop ist.
             flash("Synchronisierung startet...", 'info') # Vorläufige Nachricht
             logging.warning("Web-App Sync-Logik ist noch nicht implementiert oder relevant.")
        # >>>>> ENDE PLATZHALTER <<<<<


        # Nach der Synchronisierung (oder dem Platzhalter), leite zurück zum Dashboard.
        # Es ist wichtig, hier wieder den desktop=1 Parameter anzuhängen,
        # damit das Dashboard im Desktop-Modus bleibt und der Context Processor korrekt läuft.
        # Hole den Status wieder aus der Session für die Weiterleitung
        is_desktop_status = session.get('is_desktop_session', False)
        if is_desktop_status:
             logging.info("Leite nach Sync zurück zum Dashboard (Desktop).")
             return redirect(url_for('dashboard', desktop='1'))
        else:
             logging.info("Leite nach Sync zurück zum Dashboard (Web).")
             return redirect(url_for('dashboard'))

    # --- ENDE ROUTE FÜR DATEN SYNCHRONISIERUNG ---


    @app.route('/dashboard')
    def dashboard():
        # Prüfe, ob der Benutzer angemeldet ist
        if not session.get('user_id'):
            flash("Bitte melde dich an, um das Dashboard zu sehen.", 'warning')
            is_desktop_status = session.get('is_desktop_session', False)
            if is_desktop_status:
                 return redirect(url_for('login', desktop='1'))
            else:
                 return redirect(url_for('login'))

        user_id = session['user_id']
        today = date.today()
        year_str = request.args.get('year', str(today.year))
        month_str = request.args.get('month', str(today.month))
        q = request.args.get('q', '').strip()

        logging.info(f"Dashboard geladen für Nutzer {user_id}. Jahr: {year_str}, Monat: {month_str}, Suche: '{q}'")

        cond, params = ["user_id = %s"], [user_id]

        # --- SQL Query Building Logic (Ensure compatible with both DBs later) ---
        db_type = os.getenv("DATABASE_TYPE", "postgresql").lower()
        placeholder = "%s" if db_type == "postgresql" else "?" # Wähle Platzhalter basierend auf DB-Typ

        cond, params = [f"user_id = {placeholder}"], [user_id] # Nutze den gewählten Platzhalter

        if year_str.lower() == 'archiv':
            # SQLite Datum/Zeit Funktionen können anders sein
            if db_type == "postgresql":
                cond.append("EXTRACT(YEAR FROM date) BETWEEN 2020 AND EXTRACT(YEAR FROM CURRENT_DATE)")
            elif db_type == "sqlite":
                 cond.append("CAST(strftime('%Y', date) AS INTEGER) BETWEEN 2020 AND CAST(strftime('%Y', 'now') AS INTEGER)") # Beispiel für SQLite Datum
        else:
            try:
                year = int(year_str)
                if db_type == "postgresql":
                    cond.append(f"EXTRACT(YEAR FROM date) = {placeholder}")
                    params.append(year)
                elif db_type == "sqlite":
                    cond.append(f"CAST(strftime('%Y', date) AS INTEGER) = {placeholder}")
                    params.append(year)
            except ValueError:
                logging.warning(f"Dashboard: Ungültiges Jahresformat '{year_str}' erhalten. Jahresfilter übersprungen.")


        if year_str != 'archiv':
            try:
                month = int(month_str)
                if 1 <= month <= 12:
                    if db_type == "postgresql":
                        cond.append(f"EXTRACT(MONTH FROM date) = {placeholder}")
                        params.append(month)
                    elif db_type == "sqlite":
                         cond.append(f"CAST(strftime('%m', date) AS INTEGER) = {placeholder}")
                         params.append(month)
            except ValueError:
                pass

        if q:
            cond.append(f"(LOWER(description) LIKE {placeholder} OR LOWER(\"usage\") LIKE {placeholder})")
            like_q = f"%{q.lower()}%"
            params.extend([like_q, like_q])

        sql = f"""
            SELECT id, date, description, "usage", amount, paid, recurring_id
              FROM transactions
             WHERE {' AND '.join(cond)}
             ORDER BY date ASC, id ASC
        """

        conn = None
        rows = []
        try:
            conn = get_db_connection() # Verwendet die angepasste Funktion
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            logging.info(f"Dashboard: {len(rows)} Transaktionen gefunden.")

        except Exception as e:
            logging.error("Dashboard: Fehler beim Abrufen der Transaktionen:", exc_info=True)
            rows = []
            flash("Fehler beim Laden der Transaktionen.", 'error')
        finally:
             if conn:
                conn.close()

        transactions = []
        try:
            transactions = [
                {
                    'id': r[0],
                    'date': date.fromisoformat(r[1]) if isinstance(r[1], str) else r[1], # Konvertiere Datum bei Bedarf (SQLite gibt oft Strings zurück)
                    'description': r[2],
                    'usage': r[3],
                    'amount': float(r[4]), # Betrag als Float
                    'paid': bool(r[5]) if isinstance(r[5], int) else bool(r[5]), # SQLite gibt 0/1 (int) für BOOLEAN zurück
                    'recurring_id': r[6],
                }
                for r in rows
            ]
        except Exception as e:
             logging.error("Dashboard: Fehler beim Verarbeiten der Transaktionsergebnisse:", exc_info=True)
             transactions = []


        saldo = 0.0
        offen = 0.0
        try:
            saldo = sum(float(t.get('amount', 0)) for t in transactions)
            offen = sum(
                -float(t.get('amount', 0))
                for t in transactions
                if float(t.get('amount', 0)) < 0 and not t.get('paid', True) and t.get('recurring_id') is not None
            )
        except ValueError:
             logging.error("Dashboard: Konnte Saldo/offene Fixkosten nicht berechnen, ungültiger Betrag gefunden.", exc_info=True)
             saldo = 0.0
             offen = 0.0

        logging.info(f"Dashboard: Berechneter Saldo: {saldo}, Offene Fixkosten: {offen}")

        available_years = []
        available_months = []
        conn = None
        try:
            conn = get_db_connection() # Verwendet die angepasste Funktion
            cur = conn.cursor()
            if db_type == "postgresql":
                 cur.execute("""
                    SELECT DISTINCT EXTRACT(YEAR FROM date) AS year
                    FROM transactions
                    WHERE user_id = %s
                    ORDER BY year DESC
                """, (user_id,))
            elif db_type == "sqlite":
                 cur.execute("""
                    SELECT DISTINCT CAST(strftime('%Y', date) AS INTEGER) AS year
                    FROM transactions
                    WHERE user_id = ?
                    ORDER BY year DESC
                """, (user_id,))
            available_years = [int(row[0]) for row in cur.fetchall()]

            if year_str != 'archiv':
                 try:
                    selected_year = int(year_str)
                    if db_type == "postgresql":
                         cur.execute("""
                            SELECT DISTINCT EXTRACT(MONTH FROM date) AS month
                            FROM transactions
                            WHERE user_id = %s AND EXTRACT(YEAR FROM date) = %s
                            ORDER BY month ASC
                        """, (user_id, selected_year))
                    elif db_type == "sqlite":
                         cur.execute("""
                            SELECT DISTINCT CAST(strftime('%m', date) AS INTEGER) AS month
                            FROM transactions
                            WHERE user_id = ? AND CAST(strftime('%Y', date) AS INTEGER) = ?
                            ORDER BY month ASC
                        """, (user_id, selected_year))
                    available_months = [int(row[0]) for row in cur.fetchall()]
                 except ValueError:
                     logging.warning(f"Dashboard: Konnte Monate für ungültiges Jahr '{year_str}' nicht abrufen.")

        except Exception as e:
             logging.error("Dashboard: Fehler beim Abrufen verfügbarer Jahre/Monate:", exc_info=True)
        finally:
             if conn:
                conn.close()


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
    # ---------------------------------------------------------------------------


    # --- Blueprint Registrierungen ---
    # Stelle sicher, dass diese NACH allen @app.route Definitionen kommen
    app.register_blueprint(vorschlaege_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # --- Registriere Error Handler (Optional) ---
    # Füge diese hinzu, um benutzerdefinierte Fehlerseiten zu zeigen
    # @app.errorhandler(404)
    # def page_not_found(e):
    #     logging.warning(f"404 Not Found: {request.url}")
    #     # app_version, is_desktop etc. kommen über context_processor
    #     return render_template('404.html'), 404

    # @app.errorhandler(500)
    # def internal_server_error(e):
    #     logging.error(f"500 Internal Server Error: {request.url}", exc_info=True)
    #     # app_version, is_desktop etc. kommen über context_processor
    #     return render_template('500.html'), 500


    return app # Gebe die Flask-App Instanz zurück


# --- Hauptausführung ---
if __name__ == '__main__':
    # Erstelle die App-Instanz
    app = create_app()
    # Logge die gestartete Version beim Ausführen dieser Datei
    try:
         from core.version import __version__ as app_version_for_log
         logging.info(f"Starte Flask-App Version {app_version_for_log}")
    except ImportError:
         logging.warning("Konnte core.version nicht importieren für Startmeldung.")

    # Führe die App aus.
    # debug=True nur während der Entwicklung verwenden! In Produktion False.
    # use_reloader=False ist wichtig im Multithreading/Desktop-Kontext, um Doppelstarts zu vermeiden.
    # Passe den Port ggf. an, falls 5000 schon belegt ist.
    # host='127.0.0.1' ist Standard, kann aber explizit gesetzt werden.
    # >>> Standardmäßig Flask für Web zugänglich machen, wenn nicht im Desktop-Modus gestartet wird <<<
    # Dies erfordert, dass desktop_app.py die App anders startet oder dass der host hier angepasst wird
    # wenn pywebview verwendet wird.
    # Wenn nur app.py gestartet wird, ist host='127.0.0.1' okay.
    # Wenn desktop_app.py gestartet wird, startet es die App und Pywebview.
    # app.run(debug=False, port=5000, use_reloader=False) # Diesen Aufruf nur, wenn app.py direkt gestartet wird!

    # Die Logik zum Starten der App in desktop_app.py ist anders, dort wird webview.create_window genutzt.
    # Dieser __main__ Block hier ist nur relevant, wenn man app.py DIREKT ausführt (Web-Version).
    logging.info("Starte Flask im reinen Web-Modus (direkt via app.py).")
    # Wenn du möchtest, dass die Web-Version von extern erreichbar ist, ändere host='0.0.0.0' (Vorsicht!)
    # Für lokale Entwicklung host='127.0.0.1'
    app.run(debug=False, port=5000, use_reloader=False, host='127.0.0.1')