from bson import ObjectId
from extensions import mongo
from flask import current_app

class Message:
    @staticmethod
    def _get_collection():
        """Accès sécurisé à la collection messages"""
        if not current_app:
            raise RuntimeError("En dehors du contexte applicatif Flask")
        return mongo.db.messages