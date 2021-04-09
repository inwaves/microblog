from app import create_app, db, cli
from app.models import User, Task, Message, Notification

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    """Creates a `flask` shell context for this DB instance and models."""
    return {"db": db, "User": User, "Task": Task, "Message": Message, "Notification": Notification}
