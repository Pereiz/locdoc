from datetime import datetime, timedelta
from bson import ObjectId
from extensions import mongo

class Appointment:
    @staticmethod
    def _get_collection():
        """Accès sécurisé à la collection appointments"""
        try:
            if not mongo.db:
                raise RuntimeError("La connexion MongoDB n'est pas établie")
            return mongo.db.appointments
        except Exception as e:
            current_app.logger.error(f"Erreur DB: {str(e)}")
            raise RuntimeError(f"Erreur d'accès à la base de données: {str(e)}")
    
        

    @staticmethod
    def create(doctor_id, patient_id, slot, notes=None):
        """Crée un nouveau rendez-vous"""
        return Appointment._get_collection().insert_one({
            'doctor_id': ObjectId(doctor_id),
            'patient_id': ObjectId(patient_id),
            'slot': {
                'start': datetime.fromisoformat(slot['start']),
                'end': datetime.fromisoformat(slot['end'])
            },
            'notes': notes,
            'status': 'confirmed',  # confirmed/cancelled/completed
            'created_at': datetime.utcnow()
        }).inserted_id

    @staticmethod
    def get_by_patient(patient_id, upcoming_only=True):
        """Récupère les RDV d'un patient"""
        query = {'patient_id': ObjectId(patient_id)}
        if upcoming_only:
            query['slot.start'] = {'$gte': datetime.utcnow()}
        
        return list(Appointment._get_collection().find(query).sort('slot.start', 1))

    @staticmethod
    def get_by_doctor(doctor_id, upcoming_only=True):
        """Récupère les RDV d'un docteur"""
        query = {'doctor_id': ObjectId(doctor_id)}
        if upcoming_only:
            query['slot.start'] = {'$gte': datetime.utcnow()}
        
        return list(Appointment._get_collection().find(query).sort('slot.start', 1))

    @staticmethod
    def cancel(appointment_id):
        """Annule un rendez-vous"""
        return Appointment._get_collection().update_one(
            {'_id': ObjectId(appointment_id)},
            {'$set': {'status': 'cancelled'}}
        )
    
    @staticmethod
    def find_doctor_by_name(first_name=None, last_name=None, username=None):
        """
        Trouve un médecin par son nom ou username
        Args:
            first_name: Prénom (optionnel)
            last_name: Nom (optionnel)
            username: Nom d'utilisateur (optionnel)
        Returns:
            ObjectId: ID du médecin trouvé
        """
        query = {}
        if username:
            query["username"] = username
        else:
            if first_name:
                query["first_name"] = {"$regex": f"^{first_name}$", "$options": "i"}
            if last_name:
                query["last_name"] = {"$regex": f"^{last_name}$", "$options": "i"}

        # Recherche dans users puis vérification du rôle
        user = Appointment._get_collection().find_one(query)
        if not user:
            raise ValueError("Aucun médecin trouvé avec ces critères")
        
        # Vérifier que c'est bien un médecin
        doctor = Appointment._get_collection().find_one({"user_id": user["_id"]})
        if not doctor:
            raise ValueError("L'utilisateur trouvé n'est pas un médecin")

        return doctor["_id"]

    @staticmethod
    def get_doctor_availability(doctor_id, start_date=None, end_date=None):
        """
        Vérifie la disponibilité d'un médecin sur 7 jours
        Args:
            doctor_id: ID du médecin (str ou ObjectId)
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)
        Returns:
            dict: {
                'doctor': {info_docteur},
                'available_slots': [datetime],
                'booked_slots': [datetime]
            }
        """
        try:
            # Conversion en ObjectId si nécessaire
            doctor_oid = ObjectId(doctor_id) if not isinstance(doctor_id, ObjectId) else doctor_id

            # 1. Récupérer les infos du médecin
            doctor = Appointment._get_collection().find_one({"_id": doctor_oid})
            if not doctor:
                raise ValueError("Médecin non trouvé")

            user = Appointment._get_collection().find_one({"_id": doctor["user_id"]})
            if not user:
                raise ValueError("Utilisateur associé non trouvé")

            # 2. Définir la période par défaut (7 jours)
            now = datetime.utcnow()
            start_date = start_date or now
            end_date = end_date or (now + timedelta(days=7))

            # 3. Récupérer les rendez-vous existants
            booked_appointments = list(Appointment._get_collection().find({
                "doctor_id": doctor_oid,
                "start_time": {"$gte": start_date, "$lte": end_date},
                "status": {"$ne": "cancelled"}
            }))

            # 4. Générer les créneaux disponibles
            working_hours = doctor.get("working_hours", {})
            all_slots = Appointment.generate_time_slots(start_date, end_date, working_hours)
            booked_slots = [appt["start_time"] for appt in booked_appointments]
            available_slots = [slot for slot in all_slots if slot not in booked_slots]

            return {
                "doctor": {
                    "id": str(doctor["_id"]),
                    "username": user.get("username"),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "specialty": doctor.get("specialty")
                },
                "available_slots": available_slots,
                "booked_slots": booked_slots,
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }

        except Exception as e:
            current_app.logger.error(f"Erreur disponibilité: {str(e)}")
            raise
    
    @staticmethod
    def generate_time_slots(start_date, end_date, working_hours):
        """Génère les créneaux horaires"""
        slots = []
        current_day = start_date.date()
        end_day = end_date.date()
        
        while current_day <= end_day:
            day_name = current_day.strftime("%A").lower()
            for time_range in working_hours.get(day_name, []):
                start_time = datetime.combine(
                    current_day, 
                    datetime.strptime(time_range["start"], "%H:%M").time()
                )
                end_time = datetime.combine(
                    current_day, 
                    datetime.strptime(time_range["end"], "%H:%M").time()
                )
                
                # Génération des créneaux de 30 minutes
                while start_time < end_time:
                    if start_time >= datetime.utcnow():  # Exclure les créneaux passés
                        slots.append(start_time)
                    start_time += timedelta(minutes=30)
            
            current_day += timedelta(days=1)
        
        return slots


def generate_time_slots(start_date, end_date, working_hours):
    """
    Génère des créneaux horaires basés sur les heures de travail
    """
    slots = []
    current_date = start_date.date()
    end_date = end_date.date()
    
    while current_date <= end_date:
        day_name = current_date.strftime("%A").lower()  # lundi, mardi, etc.
        hours = working_hours.get(day_name, [])
        
        for time_range in hours:
            start_time = datetime.combine(current_date, datetime.strptime(time_range['start'], "%H:%M").time())
            end_time = datetime.combine(current_date, datetime.strptime(time_range['end'], "%H:%M").time())
            
            # Générer des créneaux de 30 minutes
            while start_time < end_time:
                slots.append(start_time)
                start_time += timedelta(minutes=30)
        
        current_date += timedelta(days=1)
    
    return slots