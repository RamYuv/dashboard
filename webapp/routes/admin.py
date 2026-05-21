import logging

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from .blueprint import main_bp
from ..auth_service import screen_required
from ..models import db
from ..services.admin_service import ADMIN_TABS, build_admin_page_context, handle_admin_form


logger = logging.getLogger(__name__)

def _admin_redirect(tab_name):
    return redirect(url_for("main.admin_screen", tab=tab_name))


def _user_management_redirect():
    return redirect(url_for("main.user_management_screen"))


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
                flash(
                    "User role updated successfully." if action == "update_role" else
                    "User teams updated successfully." if action == "update_teams" else
                    "Record created successfully.",
                    "success",
                )
            except IntegrityError as exc:
                db.session.rollback()
                logger.warning("Admin create failed for tab %s: %s", active_tab, exc)
                flash("Unable to save the record because it conflicts with existing data.", "danger")
        return _admin_redirect(active_tab)

    return render_template(
        "admin_screen.html",
        title="Admin Screen",
        **build_admin_page_context(active_tab=active_tab),
    )


@main_bp.route("/screen/admin/users", methods=["GET", "POST"])
@screen_required("user_management_screen")
def user_management_screen():
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        error = handle_admin_form(request.form)
        if error:
            db.session.rollback()
            flash(error, "danger")
        else:
            try:
                db.session.commit()
                flash(
                    "User role updated successfully." if action == "update_role" else
                    "User teams updated successfully." if action == "update_teams" else
                    "User management updated successfully.",
                    "success",
                )
            except IntegrityError as exc:
                db.session.rollback()
                logger.warning("User management update failed: %s", exc)
                flash("Unable to save the user update because it conflicts with existing data.", "danger")
        return _user_management_redirect()

    return render_template(
        "user_management_workspace.html",
        title="User Management",
        **build_admin_page_context(active_tab="users"),
    )
