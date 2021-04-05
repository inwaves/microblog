from threading import Thread

from flask import current_app
from flask_mail import Message
from app import mail


def send_async_email(app, msg):
    with current_app.app_context():
        mail.send(msg)


def send_email(subject, sender, recipients, text_body, html_body):
    """Setting up a simple mail framework to help with resetting password."""
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    Thread(target=send_async_email, args=(current_app, msg)).start()
