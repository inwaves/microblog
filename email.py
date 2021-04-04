from flask_mail import Message
from app import mail


def send_mail(subject, sender, recipients, text_body, html_body):
    """Setting up a simple mail framework to help with resetting password."""
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    mail.send(msg)
