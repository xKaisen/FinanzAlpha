# api/routes.py

from flask_restx import Api, Namespace, Resource, fields
from flask import request
from core.auth import login_user, register_user
from flask_jwt_extended import create_access_token

# Erstelle das API‑Objekt
api = Api(
    title='FinanzAlpha API',
    version='1.0',
    description='REST‑API für FinanzAlpha'
)

# Auth‑Namespace
auth_ns = Namespace('auth', description='Authentifizierungs‑Endpunkte')

login_model = auth_ns.model('Login', {
    'username': fields.String(required=True, description='Benutzername'),
    'password': fields.String(required=True, description='Passwort'),
})

register_model = auth_ns.model('Register', {
    'username': fields.String(required=True, description='Neuer Benutzername'),
    'password': fields.String(required=True, description='Neues Passwort'),
    'is_admin': fields.Boolean(description='Admin‑Rechte (nur einmal erlaubt)'),
})

token_model = auth_ns.model('Token', {
    'access_token': fields.String(description='JWT Access Token'),
})

message_model = auth_ns.model('Message', {
    'message': fields.String(description='Antwortmeldung'),
})

@auth_ns.route('/login')
class Login(Resource):
    @auth_ns.expect(login_model)
    @auth_ns.response(200, 'Erfolgreich', token_model)
    @auth_ns.response(401, 'Ungültige Anmeldedaten', message_model)
    def post(self):
        data = request.get_json() or {}
        ok, res = login_user(data.get('username','').strip(), data.get('password',''))
        if not ok:
            auth_ns.abort(401, res)
        user_id, is_admin = res
        token = create_access_token(identity={'id': user_id, 'is_admin': is_admin})
        return {'access_token': token}, 200

@auth_ns.route('/register')
class Register(Resource):
    @auth_ns.expect(register_model)
    @auth_ns.response(201, 'Registrierung erfolgreich', message_model)
    @auth_ns.response(400, 'Fehler bei der Registrierung', message_model)
    def post(self):
        data = request.get_json() or {}
        ok, msg = register_user(data.get('username','').strip(), data.get('password',''), bool(data.get('is_admin', False)))
        if not ok:
            auth_ns.abort(400, msg)
        return {'message': msg}, 201

# Registriere den Namespace beim Api‑Objekt
api.add_namespace(auth_ns, path='/api/auth')
