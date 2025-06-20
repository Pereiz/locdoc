import os
from flask import request, jsonify, current_app, url_for
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import create_access_token, get_jwt,jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from models.user import User
from utils.email import send_password_reset_email  # À implémenter
from dotenv import load_dotenv
from extensions import blacklist, mail # Importez la blacklist
from flask_mail import  Message

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
register_model1 = auth_ns.model('Register', {
    'email': fields.String(required=True, example='donagoliag@gmail.com'),
    'username' :fields.String(required=True, example='gbeto'),
    'password': fields.String(required=True, example='MotDePasseSecure123!'),
    'first_name': fields.String(required=True, example='Gbèto'),
    'last_name': fields.String(required=True, example='YENONMON'),
    'date_naissance' : fields.String(required=True, example='01/10/1990'),
    'sexe' : fields.String(required=True, enum=['F','M'], example='M'),
    'telephone' : fields.String(required=True, description='Numéro de téléphone', example='0110111214'),
    'role': fields.List(fields.String(required=True, enum=['patient'], example='patient')),
    'address': fields.Nested(address_model, required=True),
    'longitude': fields.Float(required=False, example=2.3522),
    'latitude': fields.Float(required=False, example=48.8566)
})

reset_request_model = auth_ns.model('PasswordResetRequest', {
    'email': fields.String(required=True, example='patient@locdoc.com', description="Votre mail pour recupérer votre mot de passe")
})

reset_password_model = auth_ns.model('PasswordReset', {
    'new_password': fields.String(required=True, description="New password"),
    'confirm_password': fields.String(required=True, description="Password confirmation")
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

deactivate_model = auth_ns.model('DeactivateAccount', {
    'password': fields.String(required=True, description="Mot de passe actuel")
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
            
            return {"id": str(user_id),
                    "message" : 'Allez dans votre mail pour finaliser votre processus de création de compte'
                    }, 201
            
        except RuntimeError as e:
            return {"message": f"Erreur RuntimeError : {str(e)}"}, 500
        except ValueError as e:
            return {"message": f"Erreur ValueError : {str(e)}"}, 400
        except Exception as e:
            #current_app.logger.error(f"Erreur inscription: {str(e)}")
            return {"message": f"Erreur serveur {str(e)}"}, 500

@auth_ns.route("/confirm/<token>")
class RegisterMail(Resource):
    
    def get(self, token):
        """ Cette route est pour la confirmation du mail.
        Il faut l'appeler en passant le token"""
        try:
            update_user =User.confirm_user(token)
            return f"Compte activé avec succès ! {update_user}"
        except Exception as e:
            #current_app.logger.error(f"Erreur inscription: {str(e)}")
            return {"message": f"Erreur d'activation {str(e)}"}, 500

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
            "message" : "Vous êtes connecté(e) avec succès",
            'access_token': access_token,
            'user_id': str(user['_id']),
            'role': user['role'],
            "nom" : user['last_name'],
            "prenom" : user['first_name'],
            "telephone" : user['telephone'],
            "username" : user['username']
            
        }, 200

@auth_ns.route('/deactivate-account')
class DeactivateAccount(Resource):
    @auth_ns.expect(deactivate_model)
    @jwt_required()
    def post(self):
        """Désactive le compte de l'utilisateur connecté"""
        try:
            current_user_id = get_jwt_identity()
            data = request.get_json()

            # 1. Vérifier le mot de passe
            user = User.find_by_id(current_user_id)
            if not user:
                current_app.logger.warning(f"Utilisateur introuvable ou déjà désactivé: {current_user_id}")
                return {'message': 'Utilisateur non trouvé ou compte déjà désactivé'}, 404

            if not check_password_hash(user['password'], data['password']):
                current_app.logger.warning(f"Mot de passe incorrect pour l'utilisateur: {current_user_id}")
                return {'message': 'Mot de passe incorrect'}, 401
            
            # 2. Désactiver le compte
            if User.deactivate_account(current_user_id):
                # Invalider le token JWT
                jti = get_jwt()['jti']
                blacklist.add(jti)
                current_app.logger.info(f"Compte désactivé: {current_user_id}")
                return {'message': 'Compte désactivé avec succès'}, 200
            
            return {'message': 'Échec de la désactivation'}, 400
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la désactivation: {str(e)}")
            return {'message': 'Erreur serveur'}, 500

@auth_ns.route('/request-password-reset')
class PasswordResetRequest(Resource):
    @auth_ns.expect(reset_request_model)
    def post(self):
        """Request password reset"""
        data = request.get_json()
        email = data.get('email').lower().strip()
         # Appel à la couche métier
        reset_data = User.request_password_reset(email)
        
        # Même réponse si email existe ou non (sécurité)
        if not reset_data:
            return {'message': 'Si cet email existe, un lien a été envoyé'}, 200

        reset_token, user_id = reset_data
        reset_url = url_for('auth_password_reset', token=reset_token, _external=True)
        
        try:
            User.send_reset_email(email, reset_url)
            return {'message': 'Lien de réinitialisation envoyé'}, 200
        except Exception as e:
            current_app.logger.error(f"Erreur envoi email: {str(e)}")
            return {'message': 'Erreur lors de l\'envoi du lien'}, 500


@auth_ns.route('/reset-password/<token>')
class PasswordReset(Resource):
     # Ajoutez cette méthode pour gérer les GET
    # def get(self, token):
    #     """Affiche le formulaire de réinitialisation (pour le lien dans l'email)"""
    #     # Vérifie d'abord si le token est valide
    #     user_id = User.validate_reset_token(token)
    #     if not user_id:
    #         return {'message': 'Lien invalide ou expiré'}, 400
        
    #     # Retourne une réponse simple ou redirigez vers une page frontend
    #     return {
    #         'message': 'Token valide',
    #         'token': token,
    #         'user_id': user_id
    #     }, 200

    @auth_ns.expect(reset_password_model)
    def post(self, token):
        """Réinitialisation du mot de passe avec token"""
        data = request.get_json()
        
        # Validation des mots de passe
        if data['new_password'] != data['confirm_password']:
            return {'message': 'Les mots de passe ne correspondent pas'}, 400
        
        is_valid, error_msg = User.validate_password(data['new_password'])
        if not is_valid:
            return {"error": error_msg}, 400
        
        # Vérification du token via la couche métier
        user_id = User.validate_reset_token(token)
        if not user_id:
            return {'message': 'Lien invalide ou expiré'}, 400
        
        # Réinitialisation du mot de passe
        if User.reset_password(user_id, data['new_password']):
            return {'message': 'Mot de passe mis à jour avec succès'}, 200
        else:
            return {'message': 'Échec de la mise à jour du mot de passe'}, 400

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

#@auth_ns.route('/mail')
class MailSend(Resource):
    def post(self):
        msg = Message(
            subject="Test Mail Locdoc ",
            sender=os.getenv("GMAIL_USER"),
            recipients=["prime01@duck.com","donagoliag@gmail.com"],
            body="""Prisci tu vas bien j'espère.
            Je  suis entrain de tester l'envoi de mail avec le backend pour pouvoir
            gérer la partie mot de passe oublié par mail. 
            
            Passe bonne nuit.
            
            Guillermo"""
        )
        mail.send(msg)
        return "Email envoyé !"

@auth_ns.route('/logout')
class UserLogout(Resource):
    @jwt_required()
    def post(self):
        """Déconnexion avec invalidation du token"""
        jti = get_jwt()['jti']
        blacklist.add(jti)
        return {'message': 'Déconnexion réussie, token invalidé'}, 200