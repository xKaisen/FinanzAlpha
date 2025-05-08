from flask_restx import Namespace, Resource, fields
from flask import request
from flask_jwt_extended import create_access_token

from core.db import Session
from core.models import User
from core.auth import register_user as core_register_user
import bcrypt
import hashlib

ns = Namespace('auth', description='Authentifizierungs-Endpunkte')

login_model = ns.model('Login', {
    'username': fields.String(required=True),
    'password': fields.String(required=True),
})

register_model = ns.model('Register', {
    'username': fields.String(required=True),
    'password': fields.String(required=True),
    'is_admin': fields.Boolean(),
})

token_model = ns.model('Token', {
    'access_token': fields.String(),
})

message_model = ns.model('Message', {
    'message': fields.String(),
})

@ns.route('/login')
class Login(Resource):
    @ns.expect(login_model)
    @ns.response(200, 'Erfolg', token_model)
    @ns.response(401, 'Fehler', message_model)
    def post(self):
        data = request.get_json() or {}
        username = data.get('username','').strip().lower()
        password = data.get('password','')

        ok, result = core_login := __import__('core.auth', fromlist=['login_user']).login_user(username, password)
        if not ok:
            ns.abort(401, result)

        user_id, is_admin = result
        token = create_access_token(identity={'id': user_id, 'is_admin': is_admin})
        return {'access_token': token}, 200


@ns.route('/register')
class Register(Resource):
    @ns.expect(register_model)
    @ns.response(201, 'Erfolg', message_model)
    @ns.response(400, 'Fehler', message_model)
    def post(self):
        data = request.get_json() or {}
        username = data.get('username','').strip()
        password = data.get('password','')
        is_admin = bool(data.get('is_admin', False))

        ok, msg = core_register_user(username, password, is_admin)
        if not ok:
            ns.abort(400, msg)
        return {'message': msg}, 201
