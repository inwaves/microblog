import jwt
from datetime import datetime
from hashlib import md5
from time import time

from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask_login import UserMixin
from app import db, login
from app.search import add_to_index, remove_from_index, query_index

# An association table that helps model a many-to-many relationship
# between a user's followers and "followeds".
followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id")),
)


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
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship("Task", backref="author", lazy="dynamic")
    followed = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def set_password(self, password):
        """Store the user-supplied password's hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check that the supplied password's hash matches internal hash for user."""
        return check_password_hash(self.password_hash, password)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def followed_tasks(self):
        followed = Task.query \
            .join(followers, (followers.c.followed_id == Task.user_id)) \
            .filter(followers.c.follower_id == self.id)

        # Should display the user's own tasks in the feed.
        own = Task.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Task.timestamp.desc())

    def own_tasks(self):
        own = Task.query.filter_by(user_id=self.id)
        return own.order_by(Task.timestamp.desc())

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {"reset_password": self.id,
             "exp": time() + expires_in},
            current_app.config["SECRET_KEY"], algorithm="HS256"
        )

    @staticmethod
    def verify_reset_password_token(token):
        """Decode a password given a token and a secret key."""
        try:
            id = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])["reset_password"]
        except:
            return
        return User.query.get(id)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return cls.query.filter(cls.id.in_(ids)) \
                   .order_by(db.case(when, value=cls.id)), \
               total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            "add": list(session.new),
            "update": list(session.dirty),
            "delete": list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes["add"]:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes["update"]:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes["delete"]:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj)


class Task(SearchableMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    done = db.Column(db.Boolean())
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    language = db.Column(db.String(5))
    __searchable__ = ["body"]

    def __repr__(self) -> str:
        return f"<Task {self.body} written by user {self.user_id}>"


db.event.listen(db.session, "before_commit", SearchableMixin.before_commit)
db.event.listen(db.session, "after_commit", SearchableMixin.after_commit)
