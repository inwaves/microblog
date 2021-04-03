from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# This Flask application.
app = Flask(__name__)

# Loading in the configurations via object in `config.py`
app.config.from_object(Config)

# Using extensions, define a database, a migration tool, and a login manager.
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = "login"

from app import routes, models
