# ---------------------------------------------------
# LEZIONI APP FLASK - AVVIO PRINCIPALE
# ---------------------------------------------------
import os
from dotenv import load_dotenv
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_talisman import Talisman

from fatture import fatture_bp
from routes.auth import auth_bp
from routes.lezioni import lezioni_bp
from routes.corsi import corsi_bp
from routes.archivio import archivio_bp
from routes.calendario import calendario_bp
from routes.export import export_bp
from routes.resoconto import resoconto_bp

load_dotenv()

if os.environ.get("DATABASE_URL") and "postgresql" in os.environ.get("DATABASE_URL"):
    print("Utilizzo database PostgreSQL...")
    from database_postgres import ensure_database
else:
    print("Utilizzo database SQLite...")
    from ensure_db import ensure_database

print("Verifica e inizializzazione del database...")
ensure_database()

# ---------------------------------------------------
# CREAZIONE APP FLASK
# ---------------------------------------------------
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-solo-per-sviluppo-locale-DA-CAMBIARE')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

csrf = CSRFProtect(app)
bcrypt = Bcrypt(app)

csp = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://code.jquery.com"],
    'style-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
    'font-src': ["'self'", "https://cdn.jsdelivr.net"],
    'img-src': ["'self'", "data:"],
}

Talisman(app, 
        force_https=os.environ.get('FLASK_ENV') == 'production',
        strict_transport_security=True,
        content_security_policy=csp)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "Devi effettuare il login per accedere a questa pagina."
login_manager.login_message_category = "warning"
from models.user import load_user_from_db
login_manager.user_loader(load_user_from_db)


# ---------------------------------------------------
# REGISTRAZIONE BLUEPRINTS
# ---------------------------------------------------
app.register_blueprint(fatture_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(lezioni_bp)
app.register_blueprint(corsi_bp)
app.register_blueprint(archivio_bp)
app.register_blueprint(calendario_bp)
app.register_blueprint(export_bp)
app.register_blueprint(resoconto_bp)

# ---------------------------------------------------
# AVVIO SERVER
# ---------------------------------------------------
if __name__ == "__main__":
    print(">>> Avvio applicazione Flask...")
    app.run(host="0.0.0.0", port=5000, debug=True)
