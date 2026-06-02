import logging

from flask import flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .blueprint import main_bp
from ..auth_service import current_user, login_required
from ..constants import VALID_TEAMS
from ..helpers import normalize_role, normalize_team
from ..models import Team, TeamMember, User, db


logger = logging.getLogger(__name__)


def _registration_team_choices():
    teams = Team.query.order_by(Team.team_name).all()
    if teams:
        return teams
    return [Team(team_name=team_name) for team_name in VALID_TEAMS]


def _render_register_page(team_choices):
    return render_template("register.html", team_choices=team_choices)


def _render_change_password_page(user):
    return render_template("change_password.html", user=user)


def _normalize_registration_form():
    return {
        "first_name": request.form.get("first_name", "").strip(),
        "last_name": request.form.get("last_name", "").strip(),
        "username": request.form.get("user_id", "").strip().lower(),
        "email_id": request.form.get("email", "").strip().lower(),
        "password": request.form.get("password", ""),
        "confirm_password": request.form.get("confirm_password", ""),
        "team": normalize_team(request.form.get("team", "support")),
        "role": normalize_role("user"),
    }


def _find_existing_registration_user(username, email_id):
    return (
        User.query.filter(
            (User.user_id == username) | (User.email_id == email_id)
        )
        .first()
    )


@main_bp.route("/")
def index():
    if current_user() is not None:
        return redirect(url_for("main.environment_health"))
    return redirect(url_for("main.login"))


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    team_choices = _registration_team_choices()
    if request.method == "POST":
        form_data = _normalize_registration_form()
        if not all(
            [
                form_data["first_name"],
                form_data["last_name"],
                form_data["username"],
                form_data["email_id"],
                form_data["password"],
            ]
        ):
            flash("First name, last name, user ID, email, and password are required.", "danger")
            return _render_register_page(team_choices)

        if form_data["password"] != form_data["confirm_password"]:
            flash("Passwords do not match.", "danger")
            return _render_register_page(team_choices)

        existing_user = _find_existing_registration_user(
            form_data["username"],
            form_data["email_id"],
        )
        if existing_user is not None:
            duplicate_field = (
                "user ID"
                if (existing_user.user_id or "").strip().lower() == form_data["username"]
                else "email"
            )
            flash("That {} is already registered.".format(duplicate_field), "danger")
            return _render_register_page(team_choices)

        team_record = Team.query.filter_by(team_name=form_data["team"]).first()
        if team_record is None:
            team_record = Team(team_name=form_data["team"])
            db.session.add(team_record)
            db.session.flush()

        user = User(
            username=form_data["username"],
            email_id=form_data["email_id"],
            first_name=form_data["first_name"],
            last_name=form_data["last_name"],
            name="{} {}".format(
                form_data["first_name"],
                form_data["last_name"],
            ).strip(),
            password_hash=generate_password_hash(form_data["password"]),
            role=form_data["role"],
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(
            TeamMember(
                user_id=user.user_id,
                team_id=team_record.team_id,
                role=form_data["role"],
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            logger.warning(
                "Registration failed because user %s already exists.",
                form_data["username"],
            )
            flash("That user ID or email is already registered.", "danger")
            return _render_register_page(team_choices)

        logger.info(
            "User %s registered with role=%s team=%s",
            form_data["username"],
            form_data["role"],
            form_data["team"],
        )
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("main.login"))

    return _render_register_page(team_choices)


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


@main_bp.route("/profile")
@login_required
def profile():
    user = current_user()
    return render_template("profile.html", user=user)


@main_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user.password_hash, current_password):
            flash("Current password is incorrect.", "danger")
            return _render_change_password_page(user)

        if not new_password:
            flash("New password is required.", "danger")
            return _render_change_password_page(user)

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "danger")
            return _render_change_password_page(user)

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        logger.info("User %s changed password successfully", user.user_id)
        flash("Password updated successfully.", "success")
        return redirect(url_for("main.profile"))

    return _render_change_password_page(user)
