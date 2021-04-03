from flask import render_template, flash, redirect, url_for
from app import app
from app.forms import LoginForm

user = {"username": "Andrei"}


@app.route("/")
@app.route("/index")
def index():
    todos = [
        {"id": 0, "title": "Make bed"},
        {"id": 1, "title": "Open window"},
        {"id": 2, "title": "Brew tea"},
        {"id": 3, "title": "Feed cats"},
    ]

    return render_template("index.html", title="Home", user=user, todos=todos)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        flash(
            f"Login requested for user {form.username.data}, remember_me = {form.remember_me.data}"
        )
        return redirect(url_for("index"))
    return render_template("login.html", title="Sign in", user=user, form=form)
