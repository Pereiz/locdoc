from datetime import datetime
from bson import ObjectId
from extensions import mongo

class Appointment:
    @staticmethod
    def _get_collection():
        return mongo.db.appointments

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