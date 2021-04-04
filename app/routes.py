from datetime import datetime

from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse

from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, TaskForm, ResetPasswordRequestForm, \
    ResetPasswordForm
from app.models import User, Task
from app.mail_framework import send_password_reset_email


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()


@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
@login_required
def index():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(body=form.task.data, author=current_user)
        db.session.add(task)
        db.session.commit()
        flash("Task added!")
        return redirect(url_for("index"))

    # Add pagination functionality to allow scaling up number of tasks.
    page = request.args.get("page", 1, type=int)
    tasks = current_user.followed_tasks().paginate(
        page=page,
        per_page=app.config["TASKS_PER_PAGE"],
        error_out=False,
    )

    next_url = url_for("index", page=tasks.next_num) if tasks.has_next else None
    prev_url = url_for("index", page=tasks.prev_num) if tasks.has_prev else None

    return render_template("index.html", title="Home Page", form=form, tasks=tasks.items, next_url=next_url,
                           prev_url=prev_url)


@app.route("/explore")
@login_required
def explore():
    page = request.args.get("page", 1, type=int)
    tasks = Task.query.order_by(Task.timestamp.desc()).paginate(
        page=page,
        per_page=app.config["TASKS_PER_PAGE"],
        error_out=False,
    )
    next_url = url_for("index", page=tasks.next_num) if tasks.has_next else None
    prev_url = url_for("index", page=tasks.prev_num) if tasks.has_prev else None

    return render_template("index.html", title="Explore", tasks=tasks.items, next_url=next_url,
                           prev_url=prev_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    """ Logs in the user.
        This uses flask_login to keep track of login status across pages.
        The authentication itself is done by the `User` model function.
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)

        # Let's redirect the user to the page they were
        # on prior to login, if there was one.
        next_page = request.args.get("next")
        if not next_page or url_parse(next_page).netloc != "":
            next_page = url_for("index")

        return redirect(next_page)

    return render_template("login.html", title="Sign in", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Congratulations, you are now a registered user!")
        return redirect(url_for("login"))

    return render_template("register.html", title="Register", form=form)


@app.route("/user/<username>")
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get("page", 1, type=int)
    tasks = user.own_tasks().paginate(
        page=page,
        per_page=app.config["TASKS_PER_PAGE"],
        error_out=False,
    )
    next_url = url_for("index", page=tasks.next_url) if tasks.has_next else None
    prev_url = url_for("index", page=tasks.prev_url) if tasks.has_prev else None
    form = EmptyForm()
    return render_template("user.html",
                           user=user,
                           tasks=tasks.items,
                           prev_url=prev_url,
                           next_url=next_url,
                           form=form)


@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)

    # When accessing this route via method POST, you're submitting the form.
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash("Your changes have been saved.")
        return redirect(url_for("edit_profile"))

    # When accessing via GET, i.e. the first time, show the user the form.
    elif request.method == "GET":
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me

    return render_template("edit_profile.html", title="Edit Profile", form=form)


@app.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    """Let the current user to follow a user whose page they are visiting."""
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(f"User {username} not found!")
            return redirect(url_for("index"))
        if user == current_user:
            flash("You cannot follow yourself!")
            return redirect(url_for("user", username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f"You are following {username}!")
        return redirect(url_for("user", username=username))
    else:
        return redirect(url_for("index"))


@app.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(f"User {username} not found")
            return redirect(url_for("index"))
        if user == current_user:
            flash("You cannot unfollow yourself!")
            return redirect(url_for("user", username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f"You've unfollowed {username}")
        return redirect(url_for("user", username=username))
    else:
        return redirect(url_for("index"))


@app.route("/reset_password_request", methods=["GET", "POST"])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash("Check your email for instructions to reset your password.")
        return redirect(url_for("login"))
    return render_template("reset_password_request.html", title="Reset Password", form=form)


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    # If not authenticated, decode the password token and identify the user.
    user = User.verify_reset_password_token(token)
    if not user:
        # Could not identify user.
        return redirect(url_for("index"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset.")
        return redirect(url_for("login"))
    return render_template("reset_password.html", form=form)
