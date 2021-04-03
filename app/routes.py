from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse

from app import app, db
from app.forms import LoginForm, RegistrationForm
from app.models import User


@app.route("/")
@app.route("/index")
@login_required
def index():
    todos = [
        {"id": 0, "title": "Make bed"},
        {"id": 1, "title": "Open window"},
        {"id": 2, "title": "Brew tea"},
        {"id": 3, "title": "Feed cats"},
    ]

    return render_template("index.html", title="Home", todos=todos)


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