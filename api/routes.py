# api/routes.py
from flask import Blueprint, request, jsonify
from core.db import get_db_connection
from datetime import datetime
import logging

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO)

api = Blueprint("api", __name__)

def error_response(message, status_code):
    """Hilfsfunktion für einheitliche Fehlerantworten."""
    logging.error(f"API Error: {message} (Status: {status_code})")
    return jsonify({"error": message, "success": False}), status_code

@api.route("/")
def api_root():
    return jsonify({
        "message": "FinanzAlpha API",
        "endpoints": {
            "/transactions": "GET/POST transactions",
            "/transaction/<id>": "DELETE transaction",
            "/transaction/<id>/toggle_paid": "POST toggle paid status"
        },
        "usage": "Include ?user_id=YOUR_ID&year=YYYY&month=0..12 in GET"
    })

@api.route("/transactions", methods=["GET"])
def get_transactions():
    """Transaktionen abfragen (filterbar nach user_id, year und month)."""
    user_id = request.args.get("user_id")
    year    = request.args.get("year")
    month   = request.args.get("month", "0")  # Default 0 = alle Monate

    if not user_id or not year:
        return error_response("user_id and year are required", 400)

    if not month.isdigit():
        month = "0"
    imonth = int(month)

    conditions = ["user_id = %s"]
    params     = [user_id]

    if year.lower() == "archiv":
        conditions.append("to_char(date, 'YYYY') BETWEEN '2020' AND '2024'")
    else:
        try:
            datetime(int(year), 1, 1)
        except ValueError:
            return error_response("Invalid year format", 400)
        conditions.append("to_char(date, 'YYYY') = %s")
        params.append(year)

    if 1 <= imonth <= 12:
        conditions.append("to_char(date, 'MM') = %s")
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
            colnames = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            result = [dict(zip(colnames, row)) for row in rows]
        return jsonify(result)
    except Exception as e:
        logging.exception("Error fetching transactions:")
        return error_response(f"Server error: {e}", 500)

@api.route("/transaction", methods=["POST"])
def add_transaction():
    """Neue Transaktion anlegen."""
    data = request.get_json() or {}
    missing = [f for f in ("user_id","date","description","usage","amount") if f not in data]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}", 400)

    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        return error_response("Invalid date format, use YYYY-MM-DD", 400)

    try:
        amount = float(data["amount"])
    except (ValueError, TypeError):
        return error_response("Amount must be numeric", 400)

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO transactions
                  (user_id, date, description, "usage", amount, paid)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["user_id"],
                    data["date"],
                    data["description"],
                    data["usage"],
                    amount,
                    # Set paid status based on input, default to True if not provided
                    int(bool(data.get("paid", True)))
                ),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
        return jsonify({"success": True, "id": new_id, "message": "Transaction added"}), 201

    except Exception as e:
        logging.exception("Error adding transaction:")
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
            cur.execute(
                """
                  DELETE FROM transactions
                  WHERE id = %s AND user_id = %s
                """,
                (tid, data["user_id"]),
            )
            if cur.rowcount == 0:
                return error_response("Transaction not found or access denied", 404)
            conn.commit()
        return jsonify({"success": True, "message": "Transaction deleted"})
    except Exception as e:
        logging.exception("Error deleting transaction:")
        return error_response(f"Database error: {e}", 500)

@api.route("/transaction/<int:tid>/toggle_paid", methods=["POST"])
def toggle_paid_status(tid):
    """Bezahl-Status umschalten oder setzen."""
    logging.info(f"Received toggle_paid request for transaction ID: {tid}")
    data = request.get_json() or {}
    user_id = data.get("user_id")

    if not user_id:
        return error_response("user_id required in request body", 400)

    paid_value = data.get("paid")
    logging.info(f"user_id: {user_id}, paid_value from request: {paid_value}")

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT paid, amount, recurring_id
              FROM transactions
             WHERE id = %s AND user_id = %s
        """, (tid, user_id))
        row = cur.fetchone()

        if not row:
            logging.warning(f"Transaction {tid} not found or access denied for user {user_id}")
            return error_response("Transaction not found or access denied", 404)

        current_paid, amount, rec_id = row
        logging.info(f"Current status for {tid}: paid={current_paid}, amount={amount}, recurring_id={rec_id}")

        # Only allow toggling for negative recurring transactions
        if amount >= 0 or rec_id is None:
             logging.warning(f"Attempted to toggle non-negative or non-recurring transaction {tid}")
             return error_response("Only negative recurring transactions can be toggled", 400)

        new_paid = paid_value
        if new_paid is None:
            new_paid = not current_paid
            logging.info(f"Toggling paid status from {current_paid} to {new_paid}")
        else:
            try:
                # Ensure the paid value is a boolean (or 0/1 integer)
                new_paid = bool(int(new_paid))
                logging.info(f"Setting paid status to {new_paid} based on request value")
            except (ValueError, TypeError):
                 logging.error(f"Invalid 'paid' value received: {paid_value}")
                 return error_response("Invalid paid value. Must be 0 or 1.", 400)

        cur.execute(
            "UPDATE transactions SET paid = %s WHERE id = %s AND user_id = %s",
            (new_paid, tid, user_id)
        )

        if cur.rowcount == 0:
            logging.warning(f"Update affected 0 rows for transaction {tid}, user {user_id}")
            conn.rollback()
            return error_response("Failed to update transaction status.", 500)

        conn.commit()
        logging.info(f"Successfully updated transaction {tid} paid status to {new_paid}")

        return jsonify({
            "success": True,
            "message": "Payment status updated",
            "new_status": new_paid # Return the actual new status
        })

    except Exception as e:
        logging.exception(f"An error occurred while toggling paid status for transaction {tid}:")
        if conn:
            conn.rollback()
        return error_response(f"Server error: {e}", 500)
    finally:
        if conn:
            conn.close()
            logging.info(f"Database connection closed for transaction {tid}")
