import unittest

from datetime import datetime, timedelta

from app import create_app, db
from app.models import User, Task
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"

class UserModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username="Susan")
        u.set_password("cat")
        self.assertFalse(u.check_password("dog"))
        self.assertTrue(u.check_password("cat"))

    def test_avatar(self):
        u = User(username="john", email="john@example.com")
        self.assertEqual(u.avatar(128), ('https://www.gravatar.com/avatar/'
                                         'd4c74594d841139328695756648b6bd6'
                                         '?d=identicon&s=128'))

    def test_follow(self):
        u1 = User(username="john", email="john@example.com")
        u2 = User(username="susan", email="susan@example.com")
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()

        # Should not have any followed users yet.
        self.assertEqual(u1.followed.all(), [])
        self.assertEqual(u2.followed.all(), [])

        u1.follow(u2)
        db.session.commit()

        # Validate that u1 has followed u2
        self.assertTrue(u1.is_following(u2))
        self.assertEqual(u1.followed.count(), 1)
        self.assertEqual(u1.followed.first().username, "susan")
        self.assertEqual(u2.followers.count(), 1)
        self.assertEqual(u2.followers.first().username, "john")

        u1.unfollow(u2)
        db.session.commit()
        self.assertFalse(u1.is_following(u2))
        self.assertEqual(u1.followed.count(), 0)
        self.assertEqual(u2.followers.count(), 0)

    def test_own_tasks(self):
        u1 = User(username="Andrei", email="andrei@example.com")
        db.session.add(u1)

        tasks = [
            Task(body=f"task-{i}", author=u1, timestamp=datetime.utcnow())
            for i in range(5)
        ]
        db.session.add_all(tasks)
        db.session.commit()

        self.assertEqual(u1.own_tasks().count(), len(tasks))
        self.assertEqual(u1.own_tasks().first().body, "task-4")


    def test_follow_tasks(self):
        # Create four users.
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        u3 = User(username='mary', email='mary@example.com')
        u4 = User(username='david', email='david@example.com')
        db.session.add_all([u1, u2, u3, u4])

        # Create four Tasks.
        now = datetime.utcnow()
        t1 = Task(body="Task from john", author=u1,
                  timestamp=now + timedelta(seconds=1))
        t2 = Task(body="Task from susan", author=u2,
                  timestamp=now + timedelta(seconds=4))
        t3 = Task(body="Task from mary", author=u3,
                  timestamp=now + timedelta(seconds=3))
        t4 = Task(body="Task from david", author=u4,
                  timestamp=now + timedelta(seconds=2))
        db.session.add_all([t1, t2, t3, t4])
        db.session.commit()

        # Set up the followers.
        u1.follow(u2)  # john follows susan
        u1.follow(u4)  # john follows david
        u2.follow(u3)  # susan follows mary
        u3.follow(u4)  # mary follows david
        db.session.commit()

        # Check the followed Tasks of each user.
        f1 = u1.followed_tasks().all()
        f2 = u2.followed_tasks().all()
        f3 = u3.followed_tasks().all()
        f4 = u4.followed_tasks().all()
        self.assertEqual(f1, [t2, t4, t1])
        self.assertEqual(f2, [t2, t3])
        self.assertEqual(f3, [t3, t4])
        self.assertEqual(f4, [t4])


if __name__ == '__main__':
    unittest.main(verbosity=2)
