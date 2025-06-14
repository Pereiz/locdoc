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

    # @staticmethod
    # def search(specialty=None, name=None, limit=10):
    #     """
    #     Recherche de médecins avec filtres
    #     :param specialty: Spécialité médicale (optionnel)
    #     :param name: Nom ou partie du nom (optionnel)
    #     :param limit: Nombre max de résultats
    #     :return: Liste de médecins correspondants
    #     """
    #     query = {}
        
    #     if specialty:
    #         query['specialties'] = {'$in': [specialty]}
        
    #     if name:
    #         query['$or'] = [
    #             {'first_name': {'$regex': name, '$options': 'i'}},
    #             {'last_name': {'$regex': name, '$options': 'i'}}
    #         ]
        
    #     return list(Doctor._get_collection().find(query).limit(limit))
    
    @staticmethod
    def list_all_doctors(limit=100):
        """
        Récupère la liste complète de tous les docteurs avec leurs informations utilisateur
        :param limit: Nombre max de résultats (défaut: 100)
        :return: Liste de tous les docteurs avec leurs infos utilisateur
        """
        try:
            pipeline = [
                # Jointure avec la collection user
                {
                    '$lookup': {
                        'from': 'users',
                        'localField': 'user_id',
                        'foreignField': '_id',
                        'as': 'user_info'
                    }
                },
                
                # Déplier le tableau user_info (1 docteur = 1 user)
                {'$unwind': '$user_info'},
                
                # Limiter les résultats
                {'$limit': limit},
                
                # Projection des champs nécessaires
                {
                    '$project': {
                        'doctor_id': '$_id',
                        'specialties': 1,
                        'first_name': '$user_info.first_name',
                        'last_name': '$user_info.last_name',
                        'email': '$user_info.email',
                        'telephone': '$user_info.telephone',
                        'location': '$user_info.location',
                        '_id': 0  # Exclure l'ID MongoDB par défaut
                    }
                }
            ]

            # Exécution de la requête
            doctors = list(Doctor._get_collection().aggregate(pipeline))
            return doctors

        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des docteurs: {str(e)}")
    

    @staticmethod
    def search(specialty=None, name=None, limit=10):
        """
        Recherche de médecins avec filtres combinant les collections doctor et user
        :param specialty: Spécialité médicale (optionnel)
        :param name: Nom ou partie du nom (optionnel) - recherche dans user
        :param limit: Nombre max de résultats
        :return: Liste de médecins avec leurs informations utilisateur
        """
        # Étape 1: Construire le pipeline d'agrégation
        pipeline = []
        
        # Filtre par spécialité si fournie
        if specialty:
            pipeline.append({
                '$match': {
                    'specialties': {'$in': [specialty]}
                }
            })
        
        # Jointure avec la collection user
        pipeline.append({
            '$lookup': {
                'from': 'users',
                'localField': 'user_id',  # Le champ dans doctor qui référence user
                'foreignField': '_id',    # Le champ _id dans user
                'as': 'user_info'
            }
        })
        
        # Déplier le tableau user_info (résultat de la jointure)
        pipeline.append({'$unwind': '$user_info'})
        
        # Filtre par nom si fourni (recherche dans user_info)
        if name:
            pipeline.append({
                '$match': {
                    '$or': [
                        {'user_info.first_name': {'$regex': name, '$options': 'i'}},
                        {'user_info.last_name': {'$regex': name, '$options': 'i'}}
                    ]
                }
            })
        
        # Limiter les résultats
        pipeline.append({'$limit': limit})
        
        # Projection pour formater le résultat
        pipeline.append({
            '$project': {
                'specialties': 1,
                'user_info.first_name': 1,
                'user_info.last_name': 1,
                'user_info.email': 1,
                'user_info.telephone': 1,
                # Ajoutez ici d'autres champs nécessaires
            }
        })
        
        # Étape 2: Exécuter l'agrégation
        try:
            doctors = list(Doctor._get_collection().aggregate(pipeline))
            
            # Formater les résultats pour une meilleure structure
            formatted_results = []
            for doc in doctors:
                formatted = {
                    'doctor_id': str(doc['_id']),
                    'specialties': doc.get('specialties', []),
                    'user_info': {
                        'first_name': doc['user_info']['first_name'],
                        'last_name': doc['user_info']['last_name'],
                        'email': doc['user_info']['email'],
                        'telephone': doc['user_info']['telephone']
                    }
                }
                formatted_results.append(formatted)
            
            return formatted_results
        
        except Exception as e:
            current_app.logger.error(f"Erreur recherche médecins: {str(e)}")
            raise RuntimeError("Erreur lors de la recherche des médecins")

    @staticmethod
    def search_specialite(specialty=None, user_id=None, radius_km=10, limit=10):
        """
        Recherche de médecins par spécialité dans un rayon donné autour d'un utilisateur
        """
        if not specialty:
            raise ValueError("La spécialité doit être fournie")
        
        if not user_id:
            raise ValueError("L'ID de l'utilisateur doit être fourni")

        try:
            # Récupérer les coordonnées de l'utilisateur
            from models.user import User
            if not isinstance(user_id, ObjectId):
                user_id = ObjectId(str(user_id))
            user = User.find_by_id(user_id)
            if not user:
                raise ValueError("Utilisateur introuvable")
            # if not user.get('location'):
            #     raise ValueError("L'utilisateur n'a pas de position géographique enregistrée")
            
            longitude, latitude = user['location']['coordinates']
            
            # Convertir le rayon en radians (nécessaire pour $centerSphere)
            radius_radians = radius_km / 6378.1  # 6378.1 est le rayon moyen de la Terre en km

            pipeline = [
                # Étape 1: Filtrer par spécialité
                {'$match': {'specialties': {'$in': [specialty]}}},
                
                # Étape 2: Jointure avec la collection user
                {'$lookup': {
                    'from': 'users',
                    'localField': 'user_id',
                    'foreignField': '_id',
                    'as': 'user_info'
                }},
                
                # Étape 3: Déplier le tableau user_info
                {'$unwind': '$user_info'},
                
                # Étape 4: Filtrer par distance géographique avec $geoWithin
                {'$match': {
                    'user_info.location': {
                        '$geoWithin': {
                            '$centerSphere': [
                                [longitude, latitude],
                                radius_radians
                            ]
                        }
                    }
                }},
                
                # Étape 5: Exclure l'utilisateur lui-même
                {'$match': {
                    'user_info._id': {'$ne': user_id}
                }},
                
                # Étape 6: Calculer la distance en km
                {'$addFields': {
                    'distance_km': {
                        '$multiply': [
                            {
                                '$sqrt': {
                                    '$add': [
                                        {'$pow': [{'$subtract': ['$user_info.location.coordinates[0]', longitude]}, 2]},
                                        {'$pow': [{'$subtract': ['$user_info.location.coordinates[1]', latitude]}, 2]}
                                    ]
                                }
                            },
                            111.32  # Approximation degrés -> km
                        ]
                    }
                }},
                
                # Étape 7: Trier par distance
                {'$sort': {'distance_km': 1}},
                
                # Étape 8: Limiter les résultats
                {'$limit': limit},
                
                # Étape 9: Projection
                {'$project': {
                    'specialties': 1,
                    'user_info.first_name': 1,
                    'user_info.last_name': 1,
                    'user_info.telephone': 1,
                    'user_info.location': 1,
                    'distance_km': {'$round': ['$distance_km', 2]}
                }}
            ]

            doctors = list(Doctor._get_collection().aggregate(pipeline))
            
            # Formatage des résultats
            results = []
            for doc in doctors:
                results.append({
                    'doctor_id': str(doc['_id']),
                    'specialties': doc.get('specialties', []),
                    'first_name': doc['user_info']['first_name'],
                    'last_name': doc['user_info']['last_name'],
                    'telephone': doc['user_info']['telephone'],
                    'location': doc['user_info'].get('location'),
                    'distance_km': doc.get('distance_km', 0)
                })
            
            return results

        except ValueError as ve:
            raise ve
        except Exception as e:
            raise Exception(f"Erreur lors de la recherche de médecins: {str(e)}")
    
    
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