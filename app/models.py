import json
from datetime import datetime
from hashlib import md5
from time import time

import jwt
import redis
import rq
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login
from app.search import add_to_index, query_index


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    timestamp = db.Column(db.Float, index=True, default=time)
    payload_json = db.Column(db.Text)

    def get_data(self):
        return json.loads(str(self.payload_json))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    body = db.Column(db.String(140))
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f"Message {self.body}>"


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


db.event.listen(db.session, "before_commit", SearchableMixin.before_commit)
db.event.listen(db.session, "after_commit", SearchableMixin.after_commit)

# An association table that helps model a many-to-many relationship
# between a user's followers and "followeds".
followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id")),
)


@login.user_loader
def load_user(_id):
    """Given an ID, load a user from the database for flask_login."""
    return User.query.get(int(_id))


# Multiple inheritance to fit the flask_login requirements.
# noinspection PyArgumentList
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
    messages_sent = db.relationship("Message",
                                    foreign_keys="Message.sender_id",
                                    backref="author", lazy="dynamic")

    messages_received = db.relationship("Message",
                                        foreign_keys="Message.recipient_id",
                                        backref="recipient", lazy="dynamic")

    last_message_read_time = db.Column(db.DateTime)
    notifications = db.relationship("Notification", backref="user", lazy="dynamic")
    jobs = db.relationship("Job", backref="user", lazy="dynamic")

    def new_messages(self):
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        return Message.query.filter_by(recipient=self).filter(
            Message.timestamp > last_read_time).count()

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
        # noinspection PyBroadException
        try:
            _id = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])["reset_password"]
        except:
            return
        return User.query.get(_id)

    def add_notification(self, name, data):
        # Delete the notification if it already exists.
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n

    def launch_job(self, name, description, *args, **kwargs):
        rq_job = current_app.job_queue.enqueue("app.jobs." + name, self.id, *args, **kwargs)
        job = Job(id=rq_job.get_id(), name=name, description=description, user=self)
        db.session.add(job)
        return job

    def get_jobs_in_progress(self):
        return Job.query.filter_by(user=self, complete=False).all()

    def get_job_in_progress(self, name):
        return Job.query.filter_by(user=self, name=name, complete=False).first()

    def __repr__(self) -> str:
        return f"<User {self.username}>"


@login.user_loader
def load_user(_id):
    return User.query.get(int(_id))


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


class Job(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(128), index=True)
    description = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    complete = db.Column(db.Boolean, default=False)

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get("progress", 0) if job is not None else 100
