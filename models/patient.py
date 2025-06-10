from datetime import datetime
from werkzeug.security import generate_password_hash
from extensions import mongo

class Patient:
    @staticmethod
    def create_patient(email, first_name, last_name):
        """Crée un nouveau patient"""
        #hashed_pw = generate_password_hash(password)
        return mongo.db.users.insert_one({
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'role': 'patient',
            'created_at': datetime.utcnow()
        }).inserted_id

    @staticmethod
    def find_patients(name=None, limit=10):
        """Recherche de patients"""
        query = {'role': 'patient'}
        if name:
            query['$or'] = [
                {'first_name': {'$regex': name, '$options': 'i'}},
                {'last_name': {'$regex': name, '$options': 'i'}}
            ]
        return list(mongo.db.users.find(query).limit(limit))