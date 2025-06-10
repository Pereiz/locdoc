from bson import ObjectId
from extensions import mongo
from flask import current_app
from werkzeug.security import generate_password_hash
from datetime import datetime

class Doctor:
    @staticmethod
    def _get_collection():
        """Accès sécurisé à la collection doctors"""
        if not current_app:
            raise RuntimeError("En dehors du contexte applicatif Flask")
        return mongo.db.doctors
    
    @staticmethod
    def find_by_email(email):
        """Trouve un utilisateur par email"""
        return Doctor._get_collection().find_one({'email': email})
    
    @staticmethod
    def find_by_id(id):
        """Trouve un utilisateur par son id"""
        return Doctor._get_collection().find_one({'_id': id})
    
    @staticmethod
    def create_doctor(email, user_id, rating, disponibilite, description, specialties):
        """Crée un nouveau docteur"""
        #hashed_pw = generate_password_hash(password)
        return Doctor._get_collection().insert_one({
            'email': email,
            'user_id': user_id,
            'disponibilite' : disponibilite,
            'description' : description,
            'specialties': specialties,
            'rating' : rating,
            'role': 'doctor',
            'created_at': datetime.utcnow()
        }).inserted_id

    @staticmethod
    def search(specialty=None, name=None, limit=10):
        """
        Recherche de médecins avec filtres
        :param specialty: Spécialité médicale (optionnel)
        :param name: Nom ou partie du nom (optionnel)
        :param limit: Nombre max de résultats
        :return: Liste de médecins correspondants
        """
        query = {}
        
        if specialty:
            query['specialties'] = {'$in': [specialty]}
        
        if name:
            query['$or'] = [
                {'first_name': {'$regex': name, '$options': 'i'}},
                {'last_name': {'$regex': name, '$options': 'i'}}
            ]
        
        return list(Doctor._get_collection().find(query).limit(limit))
    

    @staticmethod
    def get_availability(doctor_id):
        """
        Récupère les disponibilités d'un médecin avec validation
        Args:
            doctor_id: ID du médecin (str ou ObjectId)
        Returns:
            dict: Disponibilités structurées
        Raises:
            ValueError: Si le médecin n'existe pas
        """
        try:
            if isinstance(doctor_id, str):
                doctor_id = ObjectId(doctor_id)
                
            doctor = Doctor._get_collection().find_one(
                {'_id': doctor_id},
                {'disponibilite': 1, '_id': 0}
            )
            
            if not doctor or 'disponibilite' not in doctor:
                raise ValueError("Médecin ou disponibilités non trouvés")
                
            return doctor['disponibilite']
            
        except Exception as e:
            current_app.logger.error(f"Erreur récupération disponibilités: {str(e)}")
            raise