from flask_mail import Mail
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from itsdangerous import URLSafeTimedSerializer


mongo = PyMongo()
jwt = JWTManager()
mail = Mail()
_serializer = None
blacklist = set()

def init_serializer(secret_key):
    global _serializer
    _serializer = URLSafeTimedSerializer(secret_key)

def get_serializer():
    if _serializer is None:
        raise RuntimeError("Serializer non initialisé. Appelez d'abord init_serializer().")
    return _serializer

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in blacklist