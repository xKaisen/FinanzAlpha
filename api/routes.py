from flask import Blueprint, request, jsonify
from core.db import get_db_connection
from datetime import datetime

api = Blueprint("api", __name__)

def error_response(message, status_code):
    """Hilfsfunktion für einheitliche Fehlerantworten."""
    return jsonify({"error": message, "success": False}), status_code

@api.route("/")
def api_root():
    return jsonify({
        "message": "FinanzAlpha API",
        "endpoints": {
            "/transactions": "GET/POST transactions",
            "/transaction/<id>": "DELETE transaction",
            "/transaction/<id>/toggle_paid": "Toggle paid status"
        },
        "usage": "Include ?user_id=YOUR_ID&year=YYYY&month=0..12 in GET"
    })

@api.route("/transactions", methods=["GET"])
def get_transactions():
    """Transaktionen abfragen (filterbar nach user_id, year und month)."""
    user_id = request.args.get("user_id")
    year    = request.args.get("year")
    month   = request.args.get("month", "0")  # Default 0 = alle Monate

    # Pflicht‑Parameter prüfen
    if not user_id or not year:
        return error_response("user_id and year are required", 400)

    # month nur dann übernehmen, wenn es eine Zahl ist, sonst "0"
    if not month.isdigit():
        month = "0"
    imonth = int(month)

    # Bedingungen bauen
    conditions = ["user_id = %s"]  # Hier %s statt ?
    params     = [user_id]

    # Jahr/Archiv
    if year.lower() == "archiv":
        conditions.append("to_char(date, 'YYYY') BETWEEN '2020' AND '2024'")  # PostgreSQL-Syntax
    else:
        # validiere Jahr
        try:
            datetime(int(year), 1, 1)
        except ValueError:
            return error_response("Invalid year format", 400)
        conditions.append("to_char(date, 'YYYY') = %s")  # PostgreSQL-Syntax
        params.append(year)

    # Monat, nur wenn 1–12
    if 1 <= imonth <= 12:
        conditions.append("to_char(date, 'MM') = %s")  # PostgreSQL-Syntax
        params.append(f"{imonth:02d}")

    query = f"""
        SELECT id, date, description, "usage", amount, paid, recurring_id
        FROM transactions
        WHERE {' AND '.join(conditions)}
        ORDER BY date DESC
    """

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            # Manuelles Abrufen der Spaltennamen für Dict-Konvertierung
            colnames = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            result = []
            for row in rows:
                result.append(dict(zip(colnames, row)))
            return jsonify(result)
    except Exception as e:
        return error_response(f"Server error: {e}", 500)

@api.route("/transaction", methods=["POST"])
def add_transaction():
    """Neue Transaktion anlegen."""
    data = request.get_json() or {}
    # Pflicht‑Felder prüfen
    missing = [f for f in ("user_id","date","description","usage","amount") if f not in data]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}", 400)

    # Datum validieren
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        return error_response("Invalid date format, use YYYY-MM-DD", 400)

    # Betrag validieren
    try:
        amount = float(data["amount"])
    except (ValueError, TypeError):
        return error_response("Amount must be numeric", 400)

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO transactions
                  (user_id, date, description, "usage", amount, paid)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (  # PostgreSQL unterstützt RETURNING
                data["user_id"],
                data["date"],
                data["description"],
                data["usage"],
                amount,
                data.get("paid", 1)
            ))
            # ID direkt aus dem RETURNING-Statement abrufen
            new_id = cur.fetchone()[0]
            conn.commit()
        return jsonify({"success": True, "id": new_id, "message": "Transaction added"}), 201

    except Exception as e:
        return error_response(f"Database error: {e}", 500)

@api.route("/transaction/<int:tid>", methods=["DELETE"])
def delete_transaction(tid):
    """Transaktion löschen."""
    data = request.get_json() or {}
    if "user_id" not in data:
        return error_response("user_id required in request body", 400)

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
              DELETE FROM transactions
              WHERE id = %s AND user_id = %s
            """, (tid, data["user_id"]))
            # Anzahl der betroffenen Zeilen überprüfen
            if cur.rowcount == 0:
                return error_response("Transaction not found or access denied", 404)
            conn.commit()
        return jsonify({"success": True, "message": "Transaction deleted"})
    except Exception as e:
        return error_response(f"Database error: {e}", 500)

@api.route("/transaction/<int:tid>/toggle_paid", methods=["POST"])
def toggle_paid_status(tid):
    """Bezahl‑Status umschalten oder setzen."""
    data = request.get_json() or {}
    if "user_id" not in data:
        return error_response("user_id required in request body", 400)

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            if "paid" not in data:
                cur.execute("""
                  UPDATE transactions
                  SET paid = NOT paid
                  WHERE id = %s AND user_id = %s
                """, (tid, data["user_id"]))
            else:
                paid_int = int(bool(data["paid"]))
                cur.execute("""
                  UPDATE transactions
                  SET paid = %s
                  WHERE id = %s AND user_id = %s
                """, (paid_int, tid, data["user_id"]))

            if cur.rowcount == 0:
                return error_response("Transaction not found or access denied", 404)
            conn.commit()
        return jsonify({"success": True, "message": "Payment status updated"})
    except Exception as e:
        return error_response(f"Database error: {e}", 500)