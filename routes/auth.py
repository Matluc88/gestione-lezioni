from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from forms import LoginForm
from models.user import User, load_user_from_db
from database import db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('lezioni.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            user_obj = User(id=user["id"])
            login_user(user_obj)
            flash("Login riuscito!", "success")
            return redirect(url_for("lezioni.dashboard"))
        else:
            flash("Credenziali errate!", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout effettuato!", "info")
    return redirect(url_for("auth.login"))
