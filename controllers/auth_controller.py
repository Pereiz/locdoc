import os
from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import create_access_token, get_jwt,jwt_required, get_jwt_identity, decode_token
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from models.user import User
from utils.email import send_password_reset_email  # À implémenter
from dotenv import load_dotenv
from extensions import blacklist  # Importez la blacklist

load_dotenv()  # Charge les variables depuis .env

auth_ns = Namespace('auth', description='Authentication operations')

# Modèles Swagger
login_model = auth_ns.model('Login', {
    'email': fields.String(required=False, description='User email', example='patient@locdoc.com'),
    'username': fields.String(required=False,description='Username', example='azonvidé'),
    'password': fields.String(required=True, description='User password', example='MotDePasseSecure123!')
})
# Modèle pour l'adresse
address_model = auth_ns.model('Address', {
    'street': fields.String(required=True, example='123 Rue de la Paix'),
    'city': fields.String(required=True, example='Paris'),
    'postal_code': fields.String(required=True, example='75001'),
    'country': fields.String(required=True, example='France')
})
register_model = auth_ns.model('Register', {
    'email': fields.String(required=True, example='doctor@locdoc.com'),
    'username' :fields.String(required=True, example='azongbotor'),
    'password': fields.String(required=True, example='MotDePasseSecure123!'),
    'first_name': fields.String(required=True, example='Azongbotor'),
    'last_name': fields.String(required=True, example='YENONMON'),
    'date_naissance' : fields.String(required=True, example='01/10/1980'),
    'sexe' : fields.String(required=True, enum=['F','M'], example='M'),
    'telephone' : fields.String(required=True, description='Numéro de téléphone', example='0110111214'),
    'role': fields.List(fields.String(required=True, enum=['patient', 'doctor'], example='doctor')),
    'address': fields.Nested(address_model, required=True),
    'longitude': fields.Float(required=False, example=2.3522),
    'latitude': fields.Float(required=False, example=48.8566)
})
# register_model1 = auth_ns.model('Register', {
#     'email': fields.String(required=True, example='patient@locdoc.com'),
#     'username' :fields.String(required=True, example='azonvidé'),
#     'password': fields.String(required=True, example='MotDePasseSecure123!'),
#     'first_name': fields.String(required=True, example='Gbèto'),
#     'last_name': fields.String(required=True, example='YENONMON'),
#     'date_naissance' : fields.String(required=True, example='01/10/1990'),
#     'sexe' : fields.String(required=True, enum=['F','M'], example='M'),
#     'telephone' : fields.String(required=True, description='Numéro de téléphone', example='0110111214'),
#     'role': fields.List(fields.String(required=True, enum=['patient'], example='patient')),
#     'address': fields.Nested(address_model, required=True),
#     'longitude': fields.Float(required=False, example=2.3522),
#     'latitude': fields.Float(required=False, example=48.8566)
# })

reset_request_model = auth_ns.model('ResetRequest', {
    'email': fields.String(required=True, example='patient@locdoc.com')
})

reset_password_model = auth_ns.model('ResetPassword', {
    'token': fields.String(required=True),
    'new_password': fields.String(required=True)
})
logout_model = auth_ns.model('Logout', {
    'token': fields.String(required=True)
})
update_model = auth_ns.model('UpdateUser', {
    'first_name': fields.String(required=True, example='Gbèto'),
    'last_name': fields.String(required=True, example='YENONMON'),
    'telephone' : fields.String(required=False, description='Numéro de téléphone', example='0110111214')
})

user_model = auth_ns.model('User', {
    #'id': fields.String(attribute='_id'),
    'email': fields.String,
    'username': fields.String,
    'first_name': fields.String,
    'last_name': fields.String,
    'role': fields.List(fields.String),
    'telephone': fields.String,
    'created_at': fields.DateTime
})


@auth_ns.route('/register')
class Register(Resource):
    @auth_ns.expect(register_model)  # Spécifie le modèle attendu
    #@auth_ns.expect(register_model1)  # Spécifie le modèle attendu
    @auth_ns.response(201, 'Utilisateur créé')
    @auth_ns.response(400, 'Email déjà utilisé')
    @auth_ns.response(500, 'Erreur serveur')
    def post(self):
        """Endpoint d'inscription avec géolocalisation"""
        try:
            data = request.get_json()
            
            # Validation requise
            required_fields = ['email', 'password', 'username', 'first_name', 
                             'last_name', 'role', 'address']
            if not all(field in data for field in required_fields):
                return {'message': 'Données incomplètes'}, 400

            # Vérification de l'existence de l'utilisateur
            if User.find_by_email(data['email']):
                return {"message": f"Email {data['email']} déjà utilisé"}, 400
            if User.find_by_username(data['username']):
                return {"message": f"Username {data['username']} déjà utilisé"}, 400
            
            is_valid, error_msg = User.validate_password(data['password'])
            if not is_valid:
                return {"error": error_msg}, 400

            # Création de l'utilisateur
            user_id = User.create(
                email=data['email'],
                password=data['password'],
                username=data['username'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                telephone= data['telephone'],
                sexe=data['sexe'],
                date_naissance=data['date_naissance'],
                role=data['role'],
                address=data['address'],
                longitude=data.get('longitude'),
                latitude=data.get('latitude')
            )
            
            return {"id": str(user_id)}, 201
            
        except RuntimeError as e:
            return {"message": f"Erreur RuntimeError : {str(e)}"}, 500
        except ValueError as e:
            return {"message": f"Erreur ValueError : {str(e)}"}, 400
        except Exception as e:
            #current_app.logger.error(f"Erreur inscription: {str(e)}")
            return {"message": f"Erreur serveur {str(e)}"}, 500

@auth_ns.route('/login')
class Login(Resource):
    @auth_ns.expect(login_model)
    def post(self):
        """User login"""
        data = request.get_json()
        # Validation des données
        if not data or ('email' not in data and 'username' not in data) or 'password' not in data:
            return {'message': 'Email or username plus password required'}, 400

        # Trouver l'utilisateur par email OU username
        if 'email' in data:
            user = User.find_by_email(data['email'])
        else:
            user = User.find_by_username(data['username'])

        #return len(user)
        
        if not user or not check_password_hash(user['password'], data['password']):
            return {'message': 'Invalid credentials'}, 401

        # Créer un token JWT
        access_token = create_access_token(
            identity=str(user['_id']),
            expires_delta=timedelta(minutes=120),
            additional_claims={'role': user['role']}
        )

        return {
            'access_token': access_token,
            'user_id': str(user['_id']),
            'role': user['role']
        }, 200

@auth_ns.route('/reset-password')
class PasswordResetRequest(Resource):
    @auth_ns.expect(reset_request_model)
    def post(self):
        """Request password reset"""
        data = request.get_json()
        user = User.find_by_email(data['email'])
        
        if not user:
            return {'message': 'If this email exists, a reset link has been sent'}, 200

        # Générer un token de réinitialisation (simplifié)
        reset_token = create_access_token(
            identity=str(user['_id']),
            expires_delta=timedelta(hours=1)
        )

        # Envoyer l'email (à implémenter)
        send_password_reset_email(user['email'], reset_token)

        return {'message': 'Password reset link sent'}, 200

@auth_ns.route('/reset-password/<token>')
class PasswordReset(Resource):
    @auth_ns.expect(reset_password_model)
    def post(self, token):
        """Reset password with token"""
        data = request.get_json()
        
        try:
            # Vérifier le token (simplifié)
            #from flask_jwt_extended import decode_token
            decoded = decode_token(token)
            user_id = decoded['sub']
            
            user = User.find_by_id(user_id)
            if not user:
                return {'message': 'Invalid token'}, 400

            # Mettre à jour le mot de passe
            hashed_password = generate_password_hash(data['new_password'])
            User.update_password(user_id, hashed_password)

            return {'message': 'Password updated successfully'}, 200
        except:
            return {'message': 'Invalid or expired token'}, 400

@auth_ns.route('/info/<string:identifier>')
class UserResource(Resource):
    @jwt_required()
    @auth_ns.marshal_with(user_model)
    def get(self, identifier):
        """Récupère un utilisateur par email ou username"""
        user = User.get_user_by_identifier(identifier)
        if not user:
            auth_ns.abort(404, f"Utilisateur {identifier} non trouvé")
        return user
    

@auth_ns.route('/info_update')
class UserProfile(Resource):
    @jwt_required()
    @auth_ns.expect(update_model)
    def patch(self):
        """Mettre à jour son profil"""
        current_user_id = get_jwt_identity()
        data = auth_ns.payload or {}  # Sécurisation si payload est None
        #data = request.get_json()
        
        
        # Filtrage des champs autorisés
        allowed_fields = { 'first_name', 'last_name', 'telephone'}
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        #print(update_data)
        
        if not update_data:
            return {'message': 'Aucun champ valide à mettre à jour'}, 400
        
        if User.update_user(current_user_id, update_data):
            return {'message': 'Profil mis à jour avec succès'}, 200
        return {'message': 'Aucune modification effectuée'}, 400

#@auth_ns.route('/protected')
class Protected(Resource):
    @jwt_required()
    def get(self):
        """Test protected route"""
        current_user = get_jwt_identity()
        return {'logged_in_as': current_user}, 200

@auth_ns.route('/logout')
class UserLogout(Resource):
    @jwt_required()
    def post(self):
        """Déconnexion avec invalidation du token"""
        jti = get_jwt()['jti']
        blacklist.add(jti)
        return {'message': 'Déconnexion réussie, token invalidé'}, 200