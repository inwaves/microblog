from flask import Blueprint

bp = Blueprint("errors", __name__)

# Avoid circular dependencies.
from app.errors import handlers