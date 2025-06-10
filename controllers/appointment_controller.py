from flask_restx import Namespace, Resource, fields
from flask import request
from models.appointment import Appointment
from models.doctor import Doctor
from models.user import User

appointment_ns = Namespace('appointments', description='Gestion des rendez-vous')

# Modèles Swagger
slot_model = appointment_ns.model('TimeSlot', {
    'start': fields.DateTime(required=True, description='Date/heure de début'),
    'end': fields.DateTime(required=True, description='Date/heure de fin')
})


# JE VEUX ME BASER SUR LA DISPONIBILITE DU DOCTEUR POUR CHOISIR LES DISPONIBILITE
appointment_model = appointment_ns.model('Appointment', {
    'id': fields.String(attribute='_id'),
    'doctor_id': fields.String(required=True, example='patient@medlink.com'),
    'patient_id': fields.String(required=True, example='patient@medlink.com'),
    'slot': fields.Nested(slot_model),
    'notes': fields.String(),
    'status': fields.String(enum=['confirmed', 'cancelled', 'completed']),
    'created_at': fields.DateTime()
})

@appointment_ns.route('/')
class AppointmentResource(Resource):
    @appointment_ns.expect(appointment_model)
    #@appointment_ns.marshal_with(appointment_model, code=201)
    def post(self):
        """Prendre un nouveau rendez-vous"""
        data = request.get_json()
        
        # JE VEUX ME BASER SUR LA DISPONIBILITE DU DOCTEUR POUR CHOISIR LES DISPONIBILITE
        # Vérifier que le créneau est disponible
        try:
            doctor_schedule = Doctor.get_availability(data['doctor_id'])
            if not doctor_schedule:
                return {"message": "Médecin non trouvé ou pas de disponibilités"}, 404
                
            # Vérifiez si le créneau demandé est disponible
            requested_day = data['date'].strftime('%A').lower()  # 'lundi', 'mardi'...
            day_schedule = doctor_schedule.get(requested_day)
            
            if not day_schedule or not day_schedule.get('available'):
                return {"message": "Le médecin n'est pas disponible ce jour"}, 400

        except ValueError as e:
            return {"message": str(e)}, 400
        except Exception as e:
            return {"message": f"Erreur serveur {e}"}, 500
        
        if not Doctor.is_slot_available(doctor_schedule, data['slot']):
            return {'message': 'Créneau indisponible'}, 400
        
        # Créer le RDV
        appointment_id = Appointment.create(
            doctor_id=data['doctor_id'],
            patient_id=data['patient_id'],
            slot=data['slot'],
            notes=data.get('notes')
        )
        
        return Appointment.get_by_id(appointment_id), 201

@appointment_ns.route('/patient/<string:patient_id>')
class PatientAppointments(Resource):
    #@appointment_ns.marshal_list_with(appointment_model)
    def get(self, patient_id):
        """Liste les RDV d'un patient"""
        upcoming = request.args.get('upcoming', 'true').lower() == 'true'
        return Appointment.get_by_patient(patient_id, upcoming_only=upcoming)

@appointment_ns.route('/doctor/<string:doctor_id>')
class DoctorAppointments(Resource):
    @appointment_ns.marshal_list_with(appointment_model)
    def get(self, doctor_id):
        """Liste les RDV d'un docteur"""
        upcoming = request.args.get('upcoming', 'true').lower() == 'true'
        return Appointment.get_by_doctor(doctor_id, upcoming_only=upcoming)

@appointment_ns.route('/<string:appointment_id>/cancel')
class CancelAppointment(Resource):
    def patch(self, appointment_id):
        """Annule un rendez-vous"""
        result = Appointment.cancel(appointment_id)
        if result.modified_count == 0:
            return {'message': 'RDV non trouvé'}, 404
        return {'message': 'RDV annulé'}, 200