import sys
import json
import time

from rq import get_current_job
from flask import render_template

from app import db, create_app
from app.models import Job, User, Task
from app.mail_framework import send_email

app = create_app()
app.app_context().push()


def _set_job_progress(progress):
    rq_job = get_current_job()
    if rq_job:
        rq_job.meta["progress"] = progress
        rq_job.save_meta()
        job = Job.query.get(rq_job.get_id())
        job.user.add_notification("job_progress", {"job_id": rq_job.get_id(),
                                                   "progress": progress})
        if progress >= 100:
            job.complete = True
        db.session.commit()


def export_tasks(user_id):
    try:
        # Read user tasks from database
        user = User.query.get(user_id)
        _set_job_progress(0)
        data = []
        i = 0
        total_tasks = user.tasks.count()
        for task in user.tasks.order_by(Task.timestamp.asc()):
            data.append({"body": task.body, })
            time.sleep(5)
            i += 1
            _set_job_progress(100 * i // total_tasks)

        # Send email with data to user.
        # send_email("[Microtasks] Your tasks", sender=app.config["ADMINS"][0],
        #            recipients=[user.email],
        #            text_body=render_template("email/export_tasks.txt", user=user),
        #            html_body=render_template("email/export_tasks.html", user=user),
        #            attachments=[("tasks.json", "application/json", json.dumps({"tasks": data}, indent=4))],
        #            sync=True)
    except:
        # Handle errors
        app.logger.error("Unhandled exception", exc_info=sys.exc_info())
    finally:
        # Handle clean-up
        _set_job_progress(100)
