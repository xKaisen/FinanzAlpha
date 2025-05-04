# web/api/auth.py

from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import create_access_token
from core.auth import login_user, register_user

ns = Namespace('auth', description='Authentifizierungs-Endpunkte')

login_model = ns.model('Login', {
    'username': fields.String(required=True, description='Benutzername'),
    'password': fields.String(required=True, description='Passwort'),
})

register_model = ns.model('Register', {
    'username': fields.String(required=True, description='Neuer Benutzername'),
    'password': fields.String(required=True, description='Neues Passwort'),
    'is_admin': fields.Boolean(description='Admin-Rechte (nur einmal erlaubt)'),
})

token_model = ns.model('Token', {
    'access_token': fields.String(description='JWT Access Token'),
})

message_model = ns.model('Message', {
    'message': fields.String(description='Antwortmeldung'),
})

@ns.route('/login')
class Login(Resource):
    @ns.expect(login_model)
    @ns.response(200, 'Erfolgreich', token_model)
    @ns.response(401, 'Ungültige Anmeldedaten', message_model)
    def post(self):
        """Benutzer einloggen und JWT-Token ausgeben."""
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        ok, result = login_user(username, password)
        if not ok:
            ns.abort(401, result)
        user_id, is_admin = result
        # Identity enthält id und is_admin-Flag
        token = create_access_token(identity={'id': user_id, 'is_admin': is_admin})
        return {'access_token': token}, 200

@ns.route('/register')
class Register(Resource):
    @ns.expect(register_model)
    @ns.response(201, 'Registrierung erfolgreich', message_model)
    @ns.response(400, 'Fehler bei der Registrierung', message_model)
    def post(self):
        """Neuen Benutzer anlegen."""
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        is_admin = bool(data.get('is_admin', False))
        ok, msg = register_user(username, password, is_admin)
        if not ok:
            ns.abort(400, msg)
        return {'message': msg}, 201
