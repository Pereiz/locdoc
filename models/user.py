import re
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import current_app
from bson import ObjectId  
from extensions import mongo


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
        Crée un nouvel utilisateur avec géolocalisation
        Args:
            address: {
                "street": "123 Rue Exemple",
                "city": "Paris",
                "postal_code": "75001",
                "country": "France"
            }
            longitude/latitude: Optionnels (si non fournis, géocodage automatique)
        """

        try:
            # 1. Géocodage si coordonnées manquantes
            if not all([longitude, latitude]):
                geolocator = Nominatim(
                    user_agent="medlink_app",
                    ssl_context=certifi.where()  # Sécurité SSL
                )
                location = geolocator.geocode(
                    f"{address['street']}, {address['city']}, {address['country']}"
                )
                if not location:
                    raise ValueError("Adresse introuvable")
                longitude, latitude = location.longitude, location.latitude

            # 2. Construction du document utilisateur
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
                'activated': True,
                'created_at': datetime.utcnow(),
                'address': address,
                'location': {
                    'type': 'Point',
                    'coordinates': [longitude, latitude]
                }
            }

            # 3. Insertion sécurisée
            #result = User._get_db().insert_one(user_doc)
            result = mongo.db.users.insert_one(user_doc)
            return str(result.inserted_id)

        except GeocoderTimedOut:
            current_app.logger.error("Service de géocodage indisponible")
            raise
        except Exception as e:
            current_app.logger.error(f"Erreur création utilisateur: {str(e)}")
            raise
        
#62157357
    @staticmethod
    def find_by_email(email):
        """Trouve un utilisateur par email"""
        return User._get_db().find_one({'email': email, 'activated':True}, {'_id': 1, 'role': 1, 'email': 1, 'password': 1 })

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