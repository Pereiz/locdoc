from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from bson import ObjectId  
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.appointment import Appointment
from models.doctor import Doctor
from models.user import User
from models.message import Message

msg_ns = Namespace('msg', description='Gestion des messages')

message_model = msg_ns.model('Message', {
    'recipient_id': fields.String(required=True, example='68497468b88eb5a79bb2b2c7'),
    'content': fields.String(required=True),
})

conversation_model = msg_ns.model('Conversation', {
    'conversation_id': fields.String,
    'last_message': fields.Raw,
    'other_user': fields.Raw
})



#@msg_ns.route('/')
class MessageResource(Resource):

    def get(self):
        """Liste des messages"""
        pass

@msg_ns.route('/send')
class SendMessage(Resource):
    @msg_ns.expect(message_model)
    @jwt_required()
    def post(self):
        """Envoyer un message"""
        current_user_id = get_jwt_identity()
        data = msg_ns.payload
        
        try:
            # Détermine si l'expéditeur est un médecin
            user = User._get_db().find_one({"_id": ObjectId(current_user_id)})
            is_doctor = 'doctor' in user.get('role', [])
            
            message = Message.send_message(
                sender_id=current_user_id,
                recipient_id=data['recipient_id'],
                content=data['content'],
                is_doctor_sender=is_doctor
            )
            return Message.serialize(message), 201
        except ValueError as e:
            current_app.logger.error(f"Erreur envoi message: {str(e)}")
            return {'message': str(e)}, 400
        except Exception as e:
            current_app.logger.error(f"Erreur envoi message: {str(e)}")
            return {'message': f'Erreur serveur {str(e)}'}, 500

@msg_ns.route('/conversations')
class UserConversations(Resource):
    @jwt_required()
    def get(self):
        """Récupérer toutes les conversations de l'utilisateur"""
        current_user_id = get_jwt_identity()
        print(current_user_id)
        try:
            conversations = Message.get_user_conversations(current_user_id)
            return conversations, 200
        except Exception as e:
            return {'message': f'Erreur serveur - {str(e)}'}, 500

@msg_ns.route('/conversation/<string:conversation_id>')
@msg_ns.doc(params={'page': 'Numéro de page', 'per_page': 'Messages par page'})
class ConversationResource(Resource):
    @jwt_required()
    def get(self, conversation_id):
        """Récupérer une conversation spécifique"""
        current_user_id = get_jwt_identity()
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        
        try:
            conversation = Message.get_conversation(conversation_id, current_user_id, page, per_page)
            return conversation, 200
        except ValueError as e:
            return {'message': str(e)}, 404
        except Exception as e:
            return {'message': f'Erreur serveur - {str(e)}'}, 500