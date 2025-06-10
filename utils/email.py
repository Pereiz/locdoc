from flask_mail import Message
from flask import current_app, render_template
from extensions import mail
from threading import Thread

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_password_reset_email(email, reset_token):
    """Envoie un email de réinitialisation de mot de passe"""
    app = current_app._get_current_object()
    
    # Créez un lien de réinitialisation (à adapter selon votre frontend)
    reset_link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={reset_token}"
    
    # Créez le message email
    msg = Message(
        subject="Réinitialisation de votre mot de passe MedLink",
        sender=current_app.config['MAIL_USERNAME'],
        recipients=[email],
        html=render_template('email/reset_password.html', 
                          reset_link=reset_link,
                          app_name="MedLink")
    )
    
    # Envoi asynchrone pour ne pas bloquer l'application
    Thread(target=send_async_email, args=(app, msg)).start()