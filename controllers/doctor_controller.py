from flask_restx import Namespace, Resource, fields
from models.doctor import Doctor
from models.user import User

doctor_ns = Namespace('doctors', description='Opérations sur les médecins')

# Modèle pour les disponibilités
availability_slot_model = doctor_ns.model('AvailabilitySlot', {
    'start': fields.String(
        required=True,
        description='Heure de début au format HH:MM',
        example='09:00',
        pattern='^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'  # Validation format heure
    ),
    'end': fields.String(
        required=True,
        description='Heure de fin au format HH:MM',
        example='17:00',
        pattern='^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    )
})

# Modèle pour les jours de disponibilité
day_availability_model = doctor_ns.model('DayAvailability', {
    'morning': fields.Nested(availability_slot_model),
    'afternoon': fields.Nested(availability_slot_model),
    'available': fields.Boolean(
        required=True,
        description='Si le médecin est disponible ce jour-là',
        example=True
    )
})

# Modèle pour la documentation Swagger
doctor_model = doctor_ns.model('Doctor', {
    'id': fields.String(attribute='_id'),
    'email': fields.String(required=True, example='doctor@locdoc.com'),
    'specialties': fields.List(fields.String, example=['cardiologie'], min_items=1, unique_items=True),
    'description': fields.String(
        required=True,
        description='Description du médecin',
        example='Cardiologue expérimenté avec 10 ans de pratique',
        min_length=10,
        max_length=500
    ),
    'disponibilite': fields.Nested(doctor_ns.model('WeeklyAvailability', {
        'lundi': fields.Nested(day_availability_model),
        'mardi': fields.Nested(day_availability_model),
        'mercredi': fields.Nested(day_availability_model),
        'jeudi': fields.Nested(day_availability_model),
        'vendredi': fields.Nested(day_availability_model),
        'samedi': fields.Nested(day_availability_model),
        'dimanche': fields.Nested(day_availability_model)
    })),
    'rating': fields.Float(example=4.5,
        min=0,
        max=5,
        description='Note moyenne sur 5')
})


search_model = doctor_ns.model('SearchParams', {
    'specialty': fields.String(required=False, description='Spécialité médicale'),
    'name': fields.String(required=False, description='Nom ou partie du nom'),
    'limit': fields.Integer(required=False, default=10, description='Limite de résultats')
})

@doctor_ns.route('/search')
class DoctorSearch(Resource):
    @doctor_ns.expect(search_model)
    #@doctor_ns.marshal_list_with(doctor_model)
    def post(self):
        """Recherche de médecins avec filtres"""
        params = doctor_ns.payload
        
        results = Doctor.search(
            specialty=params.get('specialty'),
            name=params.get('name'),
            limit=params.get('limit', 10)
        )
        
        # Conversion des ObjectId en strings
        for doc in results:
            doc['_id'] = str(doc['_id'])
        
        return results
    
@doctor_ns.route('/')
class DoctorList(Resource):
    @doctor_ns.marshal_list_with(doctor_model)
    def get(self):
        """Liste tous les médecins"""
        return Doctor.search_doctors()

    @doctor_ns.expect(doctor_model)
    def post(self):
        """Crée un nouveau médecin"""
        data = doctor_ns.payload

        # Vérification de l'existence de l'utilisateur
        user = User.find_by_email(data['email'])
        if user :
            #print(f"ID: {user['_id']}, Rôle: {user['role']}")
            doctor = Doctor.find_by_email(data['email'])
            if Doctor.find_by_email(data['email']):
                return {"message" : "Ce doctor existe déjà"}, 400
            if 'doctor' in user['role']:
                doctor_id = Doctor.create_doctor(
                email=data['email'],
                description= data['description'],
                disponibilite=data['disponibilite'],
                user_id=user['_id'],
                specialties=data['specialties'],
                rating=data['rating']
                )
                return  {"id": str(doctor_id)}, 201
            else:
                return {"message": "Vous n'êtes pas docteur"}, 400
        else:
            return {"message": "utilisateur non trouvé"}, 404