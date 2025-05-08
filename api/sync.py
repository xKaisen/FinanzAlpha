# api/sync.py

from flask import Blueprint, request, jsonify
from core.db import Session
from core.models import SomeModel, LocalChangeRemote
from datetime import datetime

sync_bp = Blueprint('sync', __name__, url_prefix='/api/sync')


@sync_bp.route('/push', methods=['POST'])
def sync_push():
    session = Session()
    changes = request.get_json() or []

    for c in changes:
        table   = c.get('table')
        op      = c.get('op')
        row_id  = c.get('id')
        data    = c.get('data') or {}
        ts      = c.get('ts')

        # Tabelle → Model-Mapping (erweitere hier weitere Modelle nach Bedarf)
        if table == 'some_model':
            Model = SomeModel
        else:
            # Unbekannte Tabelle überspringen
            continue

        # CRUD-Operation ausführen
        if op == 'insert':
            session.merge(Model(**data))
        elif op == 'update':
            obj = session.get(Model, row_id)
            if obj:
                for key, val in data.items():
                    setattr(obj, key, val)
        elif op == 'delete':
            obj = session.get(Model, row_id)
            if obj:
                session.delete(obj)

        # Remote-Log anlegen
        timestamp = datetime.fromisoformat(ts) if ts else datetime.utcnow()
        session.add(
            LocalChangeRemote(
                table_name=table,
                operation=op,
                row_id=row_id,
                data=data,
                timestamp=timestamp
            )
        )

    session.commit()
    return ('', 204)


@sync_bp.route('/pull', methods=['GET'])
def sync_pull():
    since = request.args.get('since')
    cutoff = datetime.fromisoformat(since) if since else datetime.min
    session = Session()

    # Alle Remote-Änderungen nach dem Zeitpunkt abfragen
    changes = (
        session.query(LocalChangeRemote)
               .filter(LocalChangeRemote.timestamp > cutoff)
               .order_by(LocalChangeRemote.timestamp)
               .all()
    )

    payload = [
        {
            'table': c.table_name,
            'op':    c.operation,
            'id':    c.row_id,
            'data':  c.data,
            'ts':    c.timestamp.isoformat()
        }
        for c in changes
    ]

    return jsonify(payload), 200
