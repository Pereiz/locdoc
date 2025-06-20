import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from flask import current_app, url_for, render_template
from bson import ObjectId  
from extensions import mongo, mail, get_serializer
from flask_mail import Message
from itsdangerous import SignatureExpired, BadSignature
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import certifi  # Pour les connexions SSL sécurisées

class User:
    # @staticmethod
    # def _get_db():
    #     """Obtient la collection users de manière sécurisée"""
    #     if not current_app:
    #         raise RuntimeError("En dehors du contexte applicatif Flask")
    #     return mongo.db.users
    @staticmethod
    def _get_db():
        """Accès sécurisé à la collection users"""
        try:
            if not mongo.db:
                raise RuntimeError("La connexion MongoDB n'est pas établie")
            return mongo.db.users
        except Exception as e:
            current_app.logger.error(f"Erreur DB: {str(e)}")
            raise RuntimeError(f"Erreur d'accès à la base de données: {str(e)}")
    
    
    @staticmethod
    def create(email,username, password, first_name,telephone, sexe, 
               date_naissance, last_name, role,
                address, longitude=None, latitude=None):
        """
        Crée un nouvel utilisateur avec géolocalisation et envoie un email de confirmation.
        L'utilisateur n'est PAS activé tant qu'il ne confirme pas son email.
        """

        try:
            # Vérifie si l'email existe déjà (évite les doublons)
            if mongo.db.users.find_one({"email": email}):
                raise ValueError("Cet email est déjà utilisé.")
            
            # Géocodage si coordonnées manquantes
            if not all([longitude, latitude]):
                geolocator = Nominatim(
                    user_agent="locdoc_app",
                    ssl_context=certifi.where()  # Sécurité SSL
                )
                location = geolocator.geocode(
                    f"{address['street']}, {address['city']}, {address['country']}"
                )
                if not location:
                    raise ValueError("Adresse introuvable")
                longitude, latitude = location.longitude, location.latitude

            # Construction du document utilisateur
            user_doc = {
                'email': email,
                'username': username,
                'password': generate_password_hash(password),
                'first_name': first_name,
                'last_name': last_name,
                'telephone': telephone,
                'sexe': sexe,
                'date_naissance': date_naissance,
                'role': role,
                'activated': False,
                'created_at': datetime.utcnow(),
                'address': address,
                'location': {
                    'type': 'Point',
                    'coordinates': [longitude, latitude]
                }
            }

            # Insertion sécurisée
            result = mongo.db.users.insert_one(user_doc)
            user_id = str(result.inserted_id)

            # 5. Envoi de l'email de confirmation
            User._send_confirmation_email(email, user_id)

            return user_id

        except GeocoderTimedOut:
            current_app.logger.error("Service de géocodage indisponible")
            raise
        except Exception as e:
            current_app.logger.error(f"Erreur création utilisateur: {str(e)}")
            raise
    
    
    
    @staticmethod
    def _send_confirmation_email(email, user_id):
        """Génère un token et envoie l'email de confirmation."""
        try:
            serializer = get_serializer()
            
            # Génère le token
            token = serializer.dumps(user_id, salt="email-confirm")
            
            # Crée le lien de confirmation
            confirm_url = url_for('auth_register_mail', token=token, _external=True)
            
            # Rendre le template HTML
            html_body = render_template('email_confirmation.html', confirm_url=confirm_url, current_year=datetime.now().year)
        

            # Prépare l'email
            msg = Message(
                "Confirme ton email",
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[email]
            )
             # Version HTML et texte brut (pour les clients mail simples)
            msg.html = html_body
            msg.body = f"""Bonjour,

        Cliquez sur ce lien pour confirmer votre email :
        {confirm_url}

        Ce lien expirera dans 24 heures."""
            # Envoie l'email
            mail.send(msg)
            current_app.logger.info(f"Email de confirmation envoyé à {email}")
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'envoi à {email}: {str(e)}")
            raise 

    @staticmethod
    def confirm_user(token):
        """Valide le token et active le compte."""
        #serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            serializer = get_serializer()
            user_id = serializer.loads(token, salt="email-confirm", max_age=1800)  # 24h
            # Convertir en ObjectId si nécessaire (selon votre schéma MongoDB)
            from bson import ObjectId
            user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
            
            # Vérifier si l'utilisateur existe et n'est pas déjà activé
            user = mongo.db.users.find_one({"_id": user_oid})
            
            if not user:
                current_app.logger.warning(f"Utilisateur non trouvé: {user_id}")
                return False
                
            if user.get('activated'):
                current_app.logger.warning(f"Token déjà utilisé pour l'utilisateur: {user_id}")
                return False
                
            # Marquer comme activé et enregistrer la date de confirmation
            result = mongo.db.users.update_one(
                {"_id": user_oid},
                {
                    "$set": {
                        "activated": True,
                        "email_verified_at": datetime.utcnow(),
                        "confirmation_token_used": True
                    }
                }
            )
            
            if result.modified_count == 0:
                current_app.logger.error(f"Échec de l'activation pour l'utilisateur: {user_id}")
                return False
                
            current_app.logger.info(f"Compte confirmé avec succès: {user_id}")
            return True
            
        except (SignatureExpired, BadSignature) as e:
            current_app.logger.warning(f"Token invalide/expiré: {str(e)}")
            return False
        except Exception as e:
            current_app.logger.error(f"Erreur confirmation user: {str(e)}")
            raise

    #62157357
    @staticmethod
    def find_by_email(email):
        """Trouve un utilisateur par email"""
        return User._get_db().find_one({'email': email, 'activated':True})

    @staticmethod
    def find_by_id(user_id):
        """Trouve un utilisateur par ID"""
        return User._get_db().find_one({'_id': user_id})
    
    @staticmethod
    def find_by_username(username):
        """Trouve un utilisateur par son username"""
        return User._get_db().find_one({'username': username, 'activated':True})
    
    @staticmethod
    def get_user_by_identifier(identifier):
        """
        Trouve un utilisateur par email ou username
        Args:
            identifier: email ou username
        Returns:
            dict: User sans le mot de passe ou None si non trouvé
        """
        try:
            user = User._get_db().find_one({
                '$or': [
                    {'email': identifier},
                    {'username': identifier}
                ]
            }, {'password': 0})  # Exclut le mot de passe
            
            if user:
                user['_id'] = str(user['_id'])  # Convertit ObjectId en string
            return user
        except Exception as e:
            current_app.logger.error(f"Erreur recherche utilisateur: {str(e)}")
            return None


    @staticmethod
    def deactivate_account(user_id):
        """
        Désactive un compte utilisateur
        Args:
            user_id: ID de l'utilisateur à désactiver
        Returns:
            bool: True si désactivation réussie, False sinon
        """
        try:
            # Conversion sécurisée en ObjectId
            user_oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            result = mongo.db.users.update_one(
                {"_id": user_oid},
                {"$set": {
                    "activated": False,
                    "deactivated_at": datetime.utcnow()
                }}
            )
            return result.modified_count > 0
        except InvalidId:
            current_app.logger.error(f"ID utilisateur invalide: {user_id}")
            return False
        except Exception as e:
            current_app.logger.error(f"Erreur désactivation compte: {str(e)}")
            raise


    @staticmethod
    def request_password_reset(email):
        """
        Initie une demande de réinitialisation de mot de passe
        Retourne: (reset_token, user_id) ou None si l'email n'existe pas
        """
        email = email.lower().strip()
        user = mongo.db.users.find_one({"email": email, "activated": True})
        
        if not user:
            current_app.logger.info(f"Requête de mise à jour de mot de passe pour un email inexistant ou non actif: {email}")
            return None

        serializer = get_serializer()
        reset_token = serializer.dumps(str(user['_id']), salt='password-reset')
        reset_expires = datetime.utcnow() + timedelta(hours=1)

        mongo.db.users.update_one(
            {"_id": user['_id']},
            {"$set": {
                "reset_token": reset_token,
                "reset_expires": reset_expires
            }}
        )

        return reset_token, str(user['_id'])
    

    @staticmethod
    def validate_reset_token(token):
        """
        Valide un token de réinitialisation
        Retourne: user_id si valide, None sinon
        """
        serializer = get_serializer()
        try:
            user_id = serializer.loads(token, salt='password-reset', max_age=3600)
            user = mongo.db.users.find_one({
                "_id": ObjectId(user_id),
                "reset_token": token,
                "reset_expires": {"$gt": datetime.utcnow()}
            })
            return str(user['_id']) if user else None
        except (SignatureExpired, BadSignature):
            return None
        
    @staticmethod
    def reset_password(user_id, new_password):
        """
        Réinitialise le mot de passe d'un utilisateur
        Retourne: True si succès, False sinon
        """
        hashed_password = generate_password_hash(new_password)
        result = mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "password": hashed_password,
                "password_changed_at": datetime.utcnow()
            },
            "$unset": {
                "reset_token": "",
                "reset_expires": ""
            }}
        )
        return result.modified_count > 0

    @staticmethod
    def send_reset_email(email, reset_url):
        """Envoie l'email de réinitialisation"""
        msg = Message(
            "Réinitialisation de votre mot de passe LocDoc",
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.html = render_template(
            'password_reset_email.html',
            reset_url=reset_url,
            annee_courante=datetime.now().year
        )
        mail.send(msg)


        
    @staticmethod
    def update_password(user_id, new_password):
        """Met à jour le mot de passe"""
        hashed_pw = generate_password_hash(new_password)
        User._get_db().update_one(
            {'_id': user_id},
            {'$set': {'password': hashed_pw}}
        )
    
    @staticmethod
    def update_user(user_id, update_data):
        """Met à jour les informations utilisateur"""
        try:
            if not isinstance(user_id, ObjectId):
                user_id = ObjectId(str(user_id))  # Conversion sécurisée
            # update_data['updated_at'] = datetime.utcnow()
            # result = User._get_db().update_one(
            #     {'_id': user_id},
            #     {'$set': update_data}
            # )
            
            # 1. Récupérer l'utilisateur actuel
            current_user = User._get_db().find_one(
                {'_id': user_id},
                {'first_name': 1, 'last_name': 1, 'telephone': 1}
            )
            
            if not current_user:
                return False

            # 2. Filtrer les champs qui changent réellement
            changed_fields = {}
            for field in ['first_name', 'last_name', 'telephone']:
                if field in update_data and update_data[field] != current_user.get(field):
                    changed_fields[field] = update_data[field]
            
            # 3. Si aucun changement, retourner False
            if not changed_fields:
                return False
                
            # 4. Appliquer uniquement les modifications nécessaires
            result = User._get_db().update_one(
                {'_id': user_id},
                {
                    '$set': changed_fields,
                    '$currentDate': {'updated_at': True}
                }
            )
            
            return result.modified_count > 0
        except Exception as e:
            print(f"Erreur de mise à jour utilisateur: {e}")
            return False

    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """
        Valide un mot de passe avec des critères renforcés :
        - 8 caractères minimum
        - 1 majuscule
        - 1 minuscule 
        - 1 chiffre
        - 1 caractère spécial
        - Pas d'espaces
        """
        if len(password) < 8:
            return False, "8 caractères minimum requis"
            
        criteria = [
            (r'[A-Z]', "Au moins une majuscule"),
            (r'[a-z]', "Au moins une minuscule"),
            (r'[0-9]', "Au moins un chiffre"),
            (r'[^A-Za-z0-9]', "Au moins un caractère spécial"),
            (r'^\S*$', "Pas d'espaces autorisés")
        ]
        
        for pattern, error in criteria:
            if not re.search(pattern, password):
                return False, error
                
        return True, ""