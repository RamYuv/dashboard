import logging

from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .blueprint import main_bp
from ..auth_service import current_user
from ..constants import VALID_TEAMS
from ..helpers import normalize_role, normalize_team
from ..models import Team, TeamMember, User, db


logger = logging.getLogger(__name__)


def _registration_team_choices():
    teams = Team.query.order_by(Team.team_name).all()
    if teams:
        return teams
    return [Team(team_name=team_name) for team_name in VALID_TEAMS]


@main_bp.route("/")
def index():
    if current_user() is not None:
        return redirect(url_for("main.environment_health"))
    return redirect(url_for("main.login"))


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    team_choices = _registration_team_choices()
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("user_id", "").strip().lower()
        email_id = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        team = normalize_team(request.form.get("team", "support"))
        role = normalize_role("user")

        if not first_name or not last_name or not username or not email_id or not password:
            flash("First name, last name, user ID, email, and password are required.", "danger")
            return render_template("register.html", team_choices=team_choices)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", team_choices=team_choices)

        if User.query.filter_by(user_id=username).first() is not None:
            flash("That user ID is already registered.", "danger")
            return render_template("register.html", team_choices=team_choices)

        if User.query.filter_by(email_id=email_id).first() is not None:
            flash("That email is already registered.", "danger")
            return render_template("register.html", team_choices=team_choices)

        team_record = Team.query.filter_by(team_name=team).first()
        if team_record is None:
            team_record = Team(team_name=team)
            db.session.add(team_record)
            db.session.flush()

        user = User(
            username=username,
            email_id=email_id,
            first_name=first_name,
            last_name=last_name,
            name="{} {}".format(first_name, last_name).strip(),
            password_hash=generate_password_hash(password),
            role=role,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(
            TeamMember(
                user_id=user.user_id,
                team_id=team_record.team_id,
                role=role,
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            logger.warning("Registration failed because user %s already exists.", username)
            flash("That user ID or email is already registered.", "danger")
            return render_template("register.html", team_choices=team_choices)

        logger.info("User %s registered with role=%s team=%s", username, role, team)
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", team_choices=team_choices)


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not check_password_hash(user.password_hash, password):
            logger.warning("Login failed for username %s", username or "unknown")
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user.user_id
        logger.info("User %s logged in successfully", user.username)
        return redirect(url_for("main.environment_health"))

    return render_template("login.html")


@main_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        logger.info("User %s logged out", user_id)
    return redirect(url_for("main.login"))
