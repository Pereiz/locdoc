from flask_restx import Namespace, Resource, fields
from flask import request
from models.appointment import Appointment
from models.doctor import Doctor
from models.message import Message

msg_ns = Namespace('msg', description='Gestion des messages')

@msg_ns.route('/')
class MessageResource(Resource):

    def get(self):
        """Liste des messages"""
        pass