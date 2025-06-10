from flask_restx import Namespace, Resource, fields
from models.patient import Patient

patient_ns = Namespace('patient', description='Gestion des patients')

patient_model = patient_ns.model('Patient', {
    'id': fields.String(attribute='_id'),
    'first_name': fields.String(required=True),
    'last_name': fields.String(required=True),
    'email': fields.String(required=True)
})

#@patient_ns.route('/')
class PatientList(Resource):
    @patient_ns.expect(patient_model)
    #@patient_ns.marshal_list_with(patient_model)
    def get(self):
        """Liste tous les patients"""
        return Patient.find_patients()

    @patient_ns.expect(patient_model)
    @patient_ns.marshal_with(patient_model)
    def post(self):
        """Crée un nouveau patient"""
        data = patient_ns.payload
        patient_id = Patient.create_patient(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name']
        )
        return Patient.find_by_id(patient_id), 201