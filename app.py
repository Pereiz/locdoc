from flask import Flask
from flask_restx import Api
from dotenv import load_dotenv
import os
from extensions import jwt, mongo, mail, init_serializer


from controllers.auth_controller import auth_ns
from controllers.doctor_controller import doctor_ns
from controllers.patient_controller import patient_ns
from controllers.appointment_controller import appointment_ns
from controllers.msg_controller import msg_ns



load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration de l'application
    configure_app(app)
    
    # Initialisation des extensions
    initialize_extensions(app)
    
    # Vérification de la connexion MongoDB
    check_mongodb_connection(app)

    
    return app

def configure_app(app):
    """Configuration de l'application Flask"""
    # Configuration MongoDB
    mongo_uri = os.getenv("MONGODB_URI")
    #print(mongo_uri)
    if not mongo_uri:
        raise RuntimeError("❌ MONGODB_URI n'est pas défini dans les variables d'environnement")
    
    app.config["MONGO_URI"] = mongo_uri
    app.config["MONGO_CONNECT"] = False  # Important pour Atlas
    
    # Configuration JWT
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if not jwt_secret:
        raise RuntimeError("❌ JWT_SECRET_KEY n'est pas défini dans les variables d'environnement")

    app.config['JWT_SECRET_KEY'] = jwt_secret
    app.config['JWT_ALGORITHM'] = 'HS256'

    app.config["MAIL_SERVER"] = os.getenv("SMTP_SERVER")
    app.config["MAIL_PORT"] = os.getenv("SMTP_PORT")
    app.config["MAIL_USE_TLS"] = os.getenv("GMAIL_USE_TLS")
    app.config["MAIL_USERNAME"] = os.getenv("GMAIL_USER")
    app.config["MAIL_PASSWORD"] = os.getenv("GMAIL_PASSWORD")

    # Configuration itsdangerous
    app.config["ITSDANGEROUS_SECRET_KEY"] = os.getenv("ITSDANGEROUS_SECRET_KEY")
    app.config['SECURITY_PASSWORD_SALT'] = os.getenv("ITSDANGEROUS_PASSWORD_SALT") or "fallback-salt"


def initialize_extensions(app):
    """Initialisation des extensions Flask"""
    mongo.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    
    # Initialisation du serializer itsdangerous
    init_serializer(app.config['ITSDANGEROUS_SECRET_KEY'])  # Utilise la factory

def check_mongodb_connection(app):
    """Vérification de la connexion à MongoDB"""
    try:
        with app.app_context():
            # Test simple pour vérifier la connexion
            mongo.db.command('ping')
            print("✅ Connexion MongoDB établie avec succès")
            
            # Informations supplémentaires (optionnel)
            print("📊 DB Name:", mongo.db.name)
            print("📊 Collections disponibles:", mongo.db.list_collection_names())
    except Exception as e:
        print(f"❌ Échec de connexion à MongoDB: {str(e)}")
        raise RuntimeError("La connexion à la base de données a échoué") from e

# Création de l'application
app = create_app()
api = Api(app, 
          version="1.0", 
          title="LocDoc API", 
          description="API pour la gestion des rendez-vous médicaux",
          doc="/locdoc/")

# Ajout des namespaces
api.add_namespace(auth_ns)
api.add_namespace(doctor_ns)
api.add_namespace(patient_ns)
api.add_namespace(appointment_ns)
api.add_namespace(msg_ns)


port = int(os.environ.get("PORT", 5000))
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)