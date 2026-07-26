import logging
import random
from datetime import datetime, timedelta

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from .blueprint import main_bp
from ..auth_service import (
    current_user,
    login_required,
    password_change_required,
    should_redirect_to_password_change,
)
from ..helpers import normalize_role, normalize_team
from ..models import EmailDomain, PasswordChangeRequest, Team, TeamMember, User, db
from ..password_utils import (
    hash_password,
    should_force_password_change,
    sync_password_change_requirement,
    verify_password,
)
from ..services.email_service import EmailDeliveryError, SendmailEmailService


logger = logging.getLogger(__name__)
HZN_CHANGE_SESSION_KEY = "password_change_otp"
FORGOT_HZN_SESSION_KEY = "forgot_password_otp"
REGISTER_SESSION_KEY = "register_otp"
HZN_CHANGE_OTP_TTL_SECONDS = 120
REGISTER_OTP_TTL_SECONDS = 120


def _registration_team_choices():
    teams = Team.query.order_by(Team.team_name).all()
    if teams:
        return teams
    return [Team(team_name="support")]


def _registration_domain_choices():
    domains = EmailDomain.query.order_by(EmailDomain.email_domain_id).all()
    if domains:
        return domains
    return [EmailDomain(email_domain_id="example")]


def _render_register_page(team_choices, domain_choices):
    return render_template(
        "register.html",
        team_choices=team_choices,
        domain_choices=domain_choices,
    )


def _render_hzn_page(mode, user=None):
    is_forgot_password = mode == "forgot-password"
    return render_template(
        "change_password.html",
        user=user,
        page_mode=mode,
        page_title="Forgot Password" if is_forgot_password else "Change Password",
        page_heading="Forgot Password" if is_forgot_password else "Change Password",
        page_description=(
            ""
            if is_forgot_password
            else "Update your password, then verify the change with a code sent to your email."
        ),
        submit_button_label="Send Verification Code",
        cancel_url=url_for("main.login") if is_forgot_password else url_for("main.profile"),
        cancel_label="Back to Login" if is_forgot_password else "Cancel",
        success_redirect_url=url_for("main.login") if is_forgot_password else url_for("main.profile"),
        request_url=url_for("main.forgot_hzn") if is_forgot_password else url_for("main.change_hzn"),
        verify_url=(
            url_for("main.verify_forgot_hzn")
            if is_forgot_password
            else url_for("main.verify_hzn_change")
        ),
    )


def _validate_hzn_policy(password):
    if not password:
        return "New password is required."
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not any(char.isupper() for char in password):
        return "Password must include at least one uppercase letter."
    if not any(char.islower() for char in password):
        return "Password must include at least one lowercase letter."
    if not any(char.isdigit() for char in password):
        return "Password must include at least one digit."
    if not any(char in "@$!%*?&" for char in password):
        return "Password must include at least one symbol (@$!%*?&)."
    return None


def _hzn_change_email_message(user, code):
    return "\n".join([
        "A password change was requested for your Envista account.",
        "",
        "User ID: {}".format(user.user_id),
        "Verification code: {}".format(code),
        "",
        "This code will expire in 2 minutes.",
        "If you did not request this change, please ignore this email.",
    ])


def _forgot_hzn_email_message(user, code):
    return "\n".join([
        "A password reset was requested for your Envista account.",
        "",
        "User ID: {}".format(user.user_id),
        "Verification code: {}".format(code),
        "",
        "This code will expire in 2 minutes.",
        "If you did not request this reset, please ignore this email.",
    ])


def _registration_email_message(user_id, email_id, code):
    return "\n".join([
        "A new Envista account registration was requested.",
        "",
        "User ID: {}".format(user_id),
        "Email: {}".format(email_id),
        "Verification code: {}".format(code),
        "",
        "This code will expire in 2 minutes.",
        "If you did not request this registration, please ignore this email.",
    ])


def _clear_otp_session(session_key):
    session.pop(session_key, None)


def _clear_hzn_change_session():
    _clear_otp_session(HZN_CHANGE_SESSION_KEY)


def _clear_forgot_hzn_session():
    _clear_otp_session(FORGOT_HZN_SESSION_KEY)


def _clear_register_hzn_session():
    _clear_otp_session(REGISTER_SESSION_KEY)


def _clear_pending_hzn_change_requests(user_id):
    if not user_id:
        return

    PasswordChangeRequest.delete_for_user(user_id)


def _store_hzn_change_session(request_id):
    session[HZN_CHANGE_SESSION_KEY] = request_id
    session.modified = True


def _store_forgot_hzn_session(request_id):
    session[FORGOT_HZN_SESSION_KEY] = request_id
    session.modified = True


def _store_register_hzn_session(payload):
    session[REGISTER_SESSION_KEY] = payload
    session.modified = True


def _create_hzn_change_request(user, new_hzn_hash, code):
    _clear_pending_hzn_change_requests(user.user_id)
    pending_request = PasswordChangeRequest(
        user_id=user.user_id,
        new_hzn_hash=new_hzn_hash,
        verification_code=str(code),
        expires_at=datetime.utcnow() + timedelta(seconds=HZN_CHANGE_OTP_TTL_SECONDS),
        attempt_count=0,
    )
    db.session.add(pending_request)
    db.session.commit()
    return pending_request


def _delete_pending_hzn_change_request(pending_request):
    if pending_request is None:
        return
    db.session.delete(pending_request)
    db.session.commit()


def _load_pending_hzn_change_request():
    request_id = session.get(HZN_CHANGE_SESSION_KEY)
    if not request_id:
        return None
    return PasswordChangeRequest.find_by_id(request_id)


def _load_pending_forgot_hzn_request():
    request_id = session.get(FORGOT_HZN_SESSION_KEY)
    if not request_id:
        return None
    return PasswordChangeRequest.find_by_id(request_id)


def _load_pending_register_request():
    payload = session.get(REGISTER_SESSION_KEY)
    return payload if isinstance(payload, dict) else None


def _find_user_by_username(username):
    return User.find_by_username(username)


def _build_registration_email(username, email_domain):
    normalized_username = (username or "").strip().lower()
    normalized_domain = (email_domain or "").strip().lower().lstrip("@")
    if not normalized_username or not normalized_domain:
        return ""
    if "." not in normalized_domain:
        normalized_domain = normalized_domain + ".com"
    return "{}@{}".format(normalized_username, normalized_domain)


def _normalize_registration_form():
    username = request.form.get("user_id", "").strip().lower()
    email_domain = request.form.get("email_domain", "").strip().lower()
    return {
        "first_name": request.form.get("first_name", "").strip(),
        "last_name": request.form.get("last_name", "").strip(),
        "username": username,
        "email_domain": email_domain,
        "email_id": _build_registration_email(username, email_domain),
        "password": request.form.get("password", ""),
        "confirm_hzn": request.form.get("confirm_hzn", ""),
        "team": normalize_team(request.form.get("team", "support")),
        "role": normalize_role("user"),
    }


def _find_existing_registration_user(username, email_id):
    return User.find_by_user_id(username) or User.find_by_email(email_id)


def _find_or_create_registration_team(team_name):
    team_record = Team.find_by_name(team_name)
    if team_record is None:
        team_record = Team(team_name=team_name)
        db.session.add(team_record)
        db.session.flush()
    return team_record


def _build_registration_user(form_data):
    return User(
        username=form_data["username"],
        email_id=form_data["email_id"],
        first_name=form_data["first_name"],
        last_name=form_data["last_name"],
        name="{} {}".format(
            form_data["first_name"],
            form_data["last_name"],
        ).strip(),
        hzn_hash=hash_password(form_data["password"]),
        role=form_data["role"],
    )


def _finalize_successful_login(user, entered_password):
    should_change_password = sync_password_change_requirement(user, entered_password)
    if should_change_password and db.session.is_modified(user):
        db.session.commit()

    session.clear()
    session["user_id"] = user.user_id
    if should_force_password_change(user, entered_password):
        logger.info("User %s must change password before accessing the app", user.username)
        flash("Please change your temporary password before continuing.", "warning")
        return redirect(url_for("main.change_hzn"))

    logger.info("User %s logged in successfully", user.username)
    return redirect(url_for("main.environment_health"))


@main_bp.before_app_request
def enforce_required_password_change():
    if not should_redirect_to_password_change():
        return None
    flash("Please change your temporary password before continuing.", "warning")
    return redirect(url_for("main.change_hzn"))


@main_bp.route("/")
def index():
    if current_user() is not None:
        return redirect(url_for("main.environment_health"))
    return redirect(url_for("main.login"))


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    team_choices = _registration_team_choices()
    domain_choices = _registration_domain_choices()
    if request.method == "POST":
        form_data = _normalize_registration_form()
        if not all(
            [
                form_data["first_name"],
                form_data["last_name"],
                form_data["username"],
                form_data["email_domain"],
                form_data["email_id"],
                form_data["password"],
            ]
        ):
            return jsonify(
                success=False,
                error="First name, last name, user ID, email domain, and password are required.",
            ), 400

        if form_data["password"] != form_data["confirm_hzn"]:
            return jsonify(success=False, error="Passwords do not match."), 400

        policy_error = _validate_hzn_policy(form_data["password"])
        if policy_error:
            return jsonify(success=False, error=policy_error), 400

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
            return jsonify(
                success=False,
                error="That {} is already registered.".format(duplicate_field),
            ), 400

        verification_code = random.randint(100000, 999999)
        try:
            SendmailEmailService.send_message(
                subject="[Envista] Registration verification",
                recipients=[form_data["email_id"]],
                body=_registration_email_message(
                    form_data["username"],
                    form_data["email_id"],
                    verification_code,
                ),
                reply_to=form_data["email_id"],
            )
        except EmailDeliveryError as exc:
            logger.exception(
                "Registration verification email failed for user %s: %s",
                form_data["username"],
                exc,
            )
            return jsonify(
                success=False,
                error="Unable to send the verification code right now. Please try again later.",
            ), 500

        _store_register_hzn_session(
            {
                "first_name": form_data["first_name"],
                "last_name": form_data["last_name"],
                "username": form_data["username"],
                "email_domain": form_data["email_domain"],
                "email_id": form_data["email_id"],
                "password_hash": hash_password(form_data["password"]),
                "team": form_data["team"],
                "role": form_data["role"],
                "verification_code": str(verification_code),
                "expires_at": (
                    datetime.utcnow() + timedelta(seconds=REGISTER_OTP_TTL_SECONDS)
                ).isoformat(),
            }
        )

        logger.info(
            "Registration verification initiated for user %s with role=%s team=%s",
            form_data["username"],
            form_data["role"],
            form_data["team"],
        )
        return jsonify(success=True, email_id=form_data["email_id"])

    _clear_register_hzn_session()
    return _render_register_page(team_choices, domain_choices)


@main_bp.route("/verify-register", methods=["POST"])
def verify_register():
    data = request.get_json(silent=True) or {}
    submitted_code = str(data.get("code", "")).strip()
    pending_registration = _load_pending_register_request()

    if not pending_registration:
        return jsonify(success=False, error="Verification session expired. Please start again."), 400

    expires_at_raw = pending_registration.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
    except ValueError:
        expires_at = None

    if expires_at is None or expires_at < datetime.utcnow():
        _clear_register_hzn_session()
        return jsonify(success=False, error="Verification code expired. Please start again."), 400

    if submitted_code != str(pending_registration.get("verification_code", "")).strip():
        return jsonify(success=False, error="Invalid verification code."), 400

    username = pending_registration.get("username", "")
    email_id = pending_registration.get("email_id", "")
    existing_user = _find_existing_registration_user(username, email_id)
    if existing_user is not None:
        duplicate_field = (
            "user ID"
            if (existing_user.user_id or "").strip().lower() == username
            else "email"
        )
        _clear_register_hzn_session()
        return jsonify(
            success=False,
            error="That {} is already registered.".format(duplicate_field),
        ), 400

    team_record = _find_or_create_registration_team(pending_registration.get("team"))
    user = User(
        username=username,
        email_id=email_id,
        first_name=pending_registration.get("first_name", ""),
        last_name=pending_registration.get("last_name", ""),
        name="{} {}".format(
            pending_registration.get("first_name", ""),
            pending_registration.get("last_name", ""),
        ).strip(),
        hzn_hash=pending_registration.get("password_hash", ""),
        role=pending_registration.get("role", "user"),
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(
        TeamMember(
            user_id=user.user_id,
            team_id=team_record.team_id,
            role=pending_registration.get("role", "user"),
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        logger.warning(
            "Registration failed because user %s already exists.",
            username,
        )
        _clear_register_hzn_session()
        return jsonify(success=False, error="That user ID or email is already registered."), 400

    _clear_register_hzn_session()
    logger.info(
        "User %s registered with role=%s team=%s",
        username,
        pending_registration.get("role", "user"),
        pending_registration.get("team", "support"),
    )
    return jsonify(success=True)


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = _find_user_by_username(username)
        if user is None or not verify_password(user.hzn_hash, password):
            logger.warning("Login failed for username %s", username or "unknown")
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        return _finalize_successful_login(user, password)

    return render_template("login.html")


@main_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_hzn():
    if request.method == "POST":
        username = request.form.get("username", "")
        new_hzn = request.form.get("new_hzn", "")
        confirm_hzn = request.form.get("confirm_hzn", "")

        user = _find_user_by_username(username)
        if user is None:
            return jsonify(success=False, error="User ID was not found."), 400

        policy_error = _validate_hzn_policy(new_hzn)
        if policy_error:
            return jsonify(success=False, error=policy_error), 400

        if new_hzn != confirm_hzn:
            return jsonify(success=False, error="New password and confirm password do not match."), 400

        recipient = (user.email_id or "").strip()
        if not recipient:
            return jsonify(
                success=False,
                error="Your account does not have an email address configured. Please contact support.",
            ), 400

        verification_code = random.randint(100000, 999999)
        try:
            SendmailEmailService.send_message(
                subject="[Envista] Forgot password verification",
                recipients=[recipient],
                body=_forgot_hzn_email_message(user, verification_code),
                reply_to=recipient,
            )
        except EmailDeliveryError as exc:
            logger.exception(
                "Forgot password verification email failed for user %s: %s",
                user.user_id,
                exc,
            )
            return jsonify(
                success=False,
                error="Unable to send the verification code right now. Please try again later.",
            ), 500

        pending_request = _create_hzn_change_request(
            user,
            hash_password(new_hzn),
            verification_code,
        )
        _store_forgot_hzn_session(pending_request.id)
        logger.info("Forgot password verification initiated for user %s", user.user_id)
        return jsonify(success=True)

    request_id = session.get(FORGOT_HZN_SESSION_KEY)
    pending_request = PasswordChangeRequest.find_by_id(request_id) if request_id else None
    _clear_forgot_hzn_session()
    if pending_request is not None:
        _clear_pending_hzn_change_requests(pending_request.user_id)
        db.session.commit()
    return _render_hzn_page("forgot-password")


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
def change_hzn():
    user = current_user()
    if user is None:
        _clear_hzn_change_session()
        return redirect(url_for("main.login"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_hzn = request.form.get("new_hzn", "")
        confirm_hzn = request.form.get("confirm_hzn", "")

        if not verify_password(user.hzn_hash, current_password):
            return jsonify(success=False, error="Current password is incorrect."), 400

        policy_error = _validate_hzn_policy(new_hzn)
        if policy_error:
            return jsonify(success=False, error=policy_error), 400

        if new_hzn != confirm_hzn:
            return jsonify(success=False, error="New password and confirm password do not match."), 400

        recipient = (user.email_id or "").strip()
        if not recipient:
            return jsonify(
                success=False,
                error="Your account does not have an email address configured. Please contact support.",
            ), 400

        verification_code = random.randint(100000, 999999)
        try:
            SendmailEmailService.send_message(
                subject="[Envista] Password change verification",
                recipients=[recipient],
                body=_hzn_change_email_message(user, verification_code),
                reply_to=recipient,
            )
        except EmailDeliveryError as exc:
            logger.exception(
                "Password change verification email failed for user %s: %s",
                user.user_id,
                exc,
            )
            return jsonify(
                success=False,
                error="Unable to send the verification code right now. Please try again later.",
            ), 500

        pending_request = _create_hzn_change_request(
            user,
            hash_password(new_hzn),
            verification_code,
        )
        _store_hzn_change_session(pending_request.id)
        logger.info("Password change verification initiated for user %s", user.user_id)
        return jsonify(success=True)

    _clear_hzn_change_session()
    _clear_pending_hzn_change_requests(user.user_id)
    db.session.commit()
    return _render_hzn_page("change-password", user=user)


@main_bp.route("/verify-password-change", methods=["POST"])
@login_required
def verify_hzn_change():
    user = current_user()
    data = request.get_json(silent=True) or {}
    submitted_code = str(data.get("code", "")).strip()
    if user is None:
        _clear_hzn_change_session()
        return jsonify(success=False, error="Your session expired. Please log in again."), 401

    pending_change = _load_pending_hzn_change_request()

    if not pending_change:
        return jsonify(success=False, error="Verification session expired. Please start again."), 400
    if pending_change.user_id != user.user_id:
        _clear_hzn_change_session()
        return jsonify(success=False, error="Verification session is invalid for this user."), 400
    if pending_change.expires_at < datetime.utcnow():
        _delete_pending_hzn_change_request(pending_change)
        _clear_hzn_change_session()
        return jsonify(success=False, error="Verification code expired. Please start again."), 400
    if submitted_code != str(pending_change.verification_code):
        return jsonify(success=False, error="Invalid verification code."), 400

    user.hzn_hash = pending_change.new_hzn_hash or user.hzn_hash
    user.must_change_password = False
    db.session.delete(pending_change)
    db.session.commit()
    _clear_hzn_change_session()
    logger.info("User %s changed password successfully via OTP verification", user.user_id)
    return jsonify(success=True)


@main_bp.route("/verify-forgot-password", methods=["POST"])
def verify_forgot_hzn():
    data = request.get_json(silent=True) or {}
    submitted_code = str(data.get("code", "")).strip()
    pending_change = _load_pending_forgot_hzn_request()

    if not pending_change:
        return jsonify(success=False, error="Verification session expired. Please start again."), 400

    if pending_change.expires_at < datetime.utcnow():
        _delete_pending_hzn_change_request(pending_change)
        _clear_forgot_hzn_session()
        return jsonify(success=False, error="Verification code expired. Please start again."), 400

    if submitted_code != str(pending_change.verification_code):
        return jsonify(success=False, error="Invalid verification code."), 400

    user = User.find_by_user_id(pending_change.user_id)
    if user is None:
        _delete_pending_hzn_change_request(pending_change)
        _clear_forgot_hzn_session()
        return jsonify(success=False, error="User account was not found."), 400

    user.hzn_hash = pending_change.new_hzn_hash or user.hzn_hash
    user.must_change_password = False
    db.session.delete(pending_change)
    db.session.commit()
    _clear_forgot_hzn_session()
    logger.info("User %s reset password successfully via forgot-password OTP", user.user_id)
    return jsonify(success=True)
