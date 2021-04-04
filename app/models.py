from datetime import datetime
from hashlib import md5

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login

@login.user_loader
def load_user(id):
    """Given an ID, load a user from the database for flask_login."""
    return User.query.get(int(id))

# Multiple inheritance to fit the flask_login requirements.
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    tasks = db.relationship("Task", backref="author", lazy="dynamic")
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def set_password(self, password):
        """Store the user-supplied password's hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check that the supplied password's hash matches internal hash for user."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    done = db.Column(db.Boolean())
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self) -> str:
        return f"<Task {self.body} written by user {self.user_id}>"
