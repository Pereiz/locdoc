from app import app
from models.user import User

with app.app_context():
    print("✅ Contexte Flask actif")
    try:
        col = User._get_db()
        print("✅ Accès à la collection réussi")
        print("📁 Collections:", col.database.list_collection_names())
    except Exception as e:
        print("❌ Erreur:", e)
