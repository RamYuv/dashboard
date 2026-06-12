import logging
import json
from datetime import datetime

from flask import Response, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .blueprint import main_bp
from ..auth_service import current_user, screen_required
from ..models import db
from ..services.admin_service import (
    ADMIN_TABS,
    build_admin_page_context,
    export_operational_config,
    handle_admin_form,
)


logger = logging.getLogger(__name__)

def _admin_redirect(tab_name):
    return redirect(url_for("main.admin_screen", tab=tab_name))


def _flash_message_for_action(action):
    if action == "update_role":
        return "User role updated successfully."
    if action == "update_teams":
        return "User teams updated successfully."
    if action == "create_user":
        return "User created successfully."
    if action == "delete_user":
        return "User deleted successfully."
    if action.startswith("delete_"):
        return "Record deleted successfully."
    if action.startswith("update_"):
        return "Record updated successfully."
    return "Record created successfully."


def _user_management_redirect():
    return redirect(url_for("main.user_management_screen"))


def _render_user_management_page(**extra_context):
    context = build_admin_page_context(active_tab="users")
    context.update(extra_context)
    return render_template(
        "user_management_workspace.html",
        title="User Management",
        **context,
    )


@main_bp.route("/screen/admin", methods=["GET", "POST"])
@screen_required("admin_screen")
def admin_screen():
    active_tab = (request.values.get("tab") or request.values.get("entity") or ADMIN_TABS[0]).strip()
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        error = handle_admin_form(request.form)
        if error:
            db.session.rollback()
            flash(error, "danger")
        else:
            try:
                db.session.commit()
                flash(_flash_message_for_action(action), "success")
            except IntegrityError as exc:
                db.session.rollback()
                logger.warning("Admin create failed for tab %s: %s", active_tab, exc)
                flash("Unable to save the record because it conflicts with existing data.", "danger")
        return _admin_redirect(active_tab)

    return render_template(
        "admin_screen_screenshot.html",
        title="Admin Screen",
        **build_admin_page_context(active_tab=active_tab),
    )


@main_bp.route("/screen/admin/export/config", methods=["GET"])
@screen_required("admin_screen")
def admin_export_config():
    export_payload = export_operational_config()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = "envbooking-operational-config-{}.json".format(timestamp)
    return Response(
        json.dumps(export_payload, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="{}"'.format(filename),
        },
    )


@main_bp.route("/screen/admin/users", methods=["GET", "POST"])
@screen_required("user_management_screen")
def user_management_screen():
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        actor = current_user()
        target_user_id = (request.form.get("user_id") or "").strip().lower()
        if action == "delete_user" and actor is not None and target_user_id == (actor.user_id or "").strip().lower():
            flash("You cannot delete the account that is currently signed in.", "danger")
            return _user_management_redirect()
        error = handle_admin_form(request.form)
        if error:
            db.session.rollback()
            flash(error, "danger")
            if action == "create_user":
                return _render_user_management_page(
                    open_add_user_modal=True,
                    add_user_error=error,
                    add_user_form=request.form,
                )
        else:
            try:
                db.session.commit()
                flash(
                    "User created successfully." if action == "create_user" else
                    "User deleted successfully." if action == "delete_user" else
                    "User role updated successfully." if action == "update_role" else
                    "User teams updated successfully." if action == "update_teams" else
                    "User management updated successfully.",
                    "success",
                )
            except IntegrityError as exc:
                db.session.rollback()
                logger.warning("User management update failed: %s", exc)
                message = "Unable to save the user update because it conflicts with existing data."
                flash(message, "danger")
                if action == "create_user":
                    return _render_user_management_page(
                        open_add_user_modal=True,
                        add_user_error=message,
                        add_user_form=request.form,
                    )
            except SQLAlchemyError as exc:
                db.session.rollback()
                logger.exception("User management database error")
                message = "Unable to save the user because the database reported an error: {}.".format(exc.__class__.__name__)
                if getattr(exc, "orig", None):
                    message = "Unable to save the user because the database reported an error: {}.".format(exc.orig)
                flash(message, "danger")
                if action == "create_user":
                    return _render_user_management_page(
                        open_add_user_modal=True,
                        add_user_error=message,
                        add_user_form=request.form,
                    )
            except Exception as exc:
                db.session.rollback()
                logger.exception("Unexpected user management error")
                message = "Unable to save the user because of an unexpected server error."
                flash(message, "danger")
                if action == "create_user":
                    return _render_user_management_page(
                        open_add_user_modal=True,
                        add_user_error=message,
                        add_user_form=request.form,
                    )
        return _user_management_redirect()

    return _render_user_management_page()
