import json
import math
from bson import ObjectId, json_util
from extensions import mongo
from flask import current_app
from datetime import datetime
from models.user import User


class Message:
    @staticmethod
    def _get_db():
        """Accès sécurisé à la collection messages"""
        if not current_app:
            raise RuntimeError("En dehors du contexte applicatif Flask")
        return mongo.db.messages
    
    @staticmethod
    def generate_conversation_id(user1_id, user2_id):
        """Génère un ID de conversation unique et ordonné"""
        ids = sorted([str(user1_id), str(user2_id)])
        return f"{ids[0]}_{ids[1]}"
    
    @staticmethod
    def serialize_message(message):
        """Convertit un message MongoDB en JSON sérialisable"""
        if message and '_id' in message:
            message['_id'] = str(message['_id'])
        if message and 'sender_id' in message:
            message['sender_id'] = str(message['sender_id'])
        if message and 'recipient_id' in message:
            message['recipient_id'] = str(message['recipient_id'])
        return message
    
    @staticmethod
    def serialize(data):
        """Sérialise les données MongoDB (avec ObjectId et datetime) en JSON"""
        return json.loads(json_util.dumps(data))

    @staticmethod
    def send_message(sender_id, recipient_id, content, is_doctor_sender):
        """
        Envoie un message entre utilisateurs
        Args:
            sender_id: ID de l'expéditeur
            recipient_id: ID du destinataire
            content: Contenu du message
            is_doctor_sender: Booléen indiquant si l'expéditeur est un médecin
        Returns:
            dict: Message créé
        """
        # Vérifier les types d'utilisateurs
        sender = User._get_db().find_one({"_id": ObjectId(sender_id)})
        recipient = User._get_db().find_one({"_id": ObjectId(recipient_id)})
        
        if not sender:
            raise ValueError("Utilisateur sender non trouvé")
        if not recipient:
            raise ValueError("Utilisateur recipient non trouvé")
            
        # Vérifier les permissions (patient ne peut envoyer qu'à un médecin)
        if 'patient' in sender['role'] and 'doctor' not in recipient['role']:
            raise ValueError("Un patient ne peut envoyer des messages qu'à un médecin")

        conversation_id = Message.generate_conversation_id(sender_id, recipient_id)
        
        message = {
            "conversation_id": conversation_id,
            "sender_id": ObjectId(sender_id),
            "recipient_id": ObjectId(recipient_id),
            "content": content,
            "is_doctor_sender": is_doctor_sender,
            "timestamp": datetime.utcnow(),
            "read": False
        }
        
        # Insertion du message
        result = Message._get_db().insert_one(message)
        message['_id'] = result.inserted_id
        
        # Mise à jour/mise à jour de la conversation
        mongo.db.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_message": message['_id'],
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "participants": [ObjectId(sender_id), ObjectId(recipient_id)],
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return Message.serialize_message(message)

    @staticmethod
    def get_conversation(conversation_id, user_id, page=1, per_page=20):
        """
        Récupère une conversation avec pagination
        Args:
            conversation_id: ID de la conversation au format "id1_id2" (string)
            user_id: ID de l'utilisateur demandant la conversation (string)
            page: Numéro de page
            per_page: Messages par page
        Returns:
            dict: Conversation et messages avec sérialisation JSON safe
        """
        # Vérification que l'utilisateur fait partie de la conversation
        participant_ids = conversation_id.split('_')
        if user_id not in participant_ids:
            raise ValueError("Accès non autorisé à cette conversation")

        # Trouver la conversation (sans conversion ObjectId pour conversation_id)
        conversation = mongo.db.conversations.find_one(
            {"conversation_id": conversation_id}
        )
        
        if not conversation:
            raise ValueError("Conversation non trouvée")
        
        # Récupération des messages paginés
        messages = list(mongo.db.messages.find(
            {"conversation_id": conversation_id}
        ).sort("timestamp", -1).skip((page - 1) * per_page).limit(per_page))
        
        # Fonction de conversion améliorée
        def sanitize(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [sanitize(item) for item in obj]
            return obj
        
        # Préparation de la réponse
        response = {
            "conversation_id": conversation_id,
            "participants": participant_ids,
            "messages": [sanitize(msg) for msg in messages],
            "conversation_details": {
                "created_at": sanitize(conversation.get('created_at')),
                "updated_at": sanitize(conversation.get('updated_at')),
                "last_message_id": sanitize(conversation.get('last_message'))
            },
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_messages": mongo.db.messages.count_documents(
                    {"conversation_id": conversation_id}
                ),
                "total_pages": math.ceil(mongo.db.messages.count_documents(
                    {"conversation_id": conversation_id}
                ) / per_page)
            }
        }
    
        return response

    @staticmethod
    def get_user_conversations(user_id):
        """
        Récupère toutes les conversations d'un utilisateur
        Args:
            user_id: ID de l'utilisateur
        Returns:
            list: Liste des conversations avec dernier message
        """
        try:
            user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
            
            # Pipeline d'agrégation optimisé
            pipeline = [
                {
                    "$match": {"participants": user_oid}
                },
                {
                    "$sort": {"updated_at": -1}
                },
                {
                    "$lookup": {
                        "from": "messages",
                        "let": {"last_msg_id": "$last_message"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {"$eq": ["$_id", "$$last_msg_id"]}
                                }
                            },
                            {
                                "$limit": 1
                            }
                        ],
                        "as": "last_message"
                    }
                },
                {
                    "$unwind": {
                        "path": "$last_message",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "let": {"participants": "$participants"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {"$in": ["$_id", "$$participants"]}
                                }
                            },
                            {
                                "$project": {
                                    "_id": 1,
                                    "username": 1,
                                    "email": 1,
                                    "first_name": 1,
                                    "last_name": 1,
                                    "role": 1
                                }
                            }
                        ],
                        "as": "participants_info"
                    }
                },
                {
                    "$addFields": {
                        "other_user": {
                            "$arrayElemAt": [
                                {
                                    "$filter": {
                                        "input": "$participants_info",
                                        "as": "participant",
                                        "cond": {"$ne": ["$$participant._id", user_oid]}
                                    }
                                },
                                0
                            ]
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "conversation_id": 1,
                        "last_message": 1,
                        "updated_at": 1,
                        "unread_count": 1,
                        "other_user": {
                            "_id": 1,
                            "username": 1,
                            "email": 1,
                            "first_name": 1,
                            "last_name": 1,
                            "role": 1
                        }
                    }
                }
            ]
            
            conversations = list(mongo.db.conversations.aggregate(
                pipeline,
                allowDiskUse=True,
                maxTimeMS=30000))
            
            # Sérialisation avec gestion des erreurs
            try:
                serialized = json.loads(json_util.dumps(conversations))
                return serialized
            except Exception as serialize_error:
                current_app.logger.error(f"Erreur sérialisation: {str(serialize_error)}")
                raise ValueError("Erreur de format des données")
        except Exception as e:
            current_app.logger.error(f"Erreur récupération conversations: {str(e)}")
            raise ValueError("Erreur lors de la récupération des conversations")