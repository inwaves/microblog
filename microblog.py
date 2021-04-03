from app import app, db
from app.models import User, Task

@app.shell_context_processor
def make_shell_context():
    """Creates a `flask` shell context for this DB instance and models."""
    return {"db": db, "User": User, "Task": Task}