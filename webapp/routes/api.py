import csv
from datetime import datetime
from io import StringIO

from flask import Response, jsonify, request

from .blueprint import main_bp
from ..auth_service import can_access_env_team_screen, current_user, login_required
from ..helpers import (
    filter_bookings_for_history,
    get_environment_types,
    get_environments,
    list_environment_operations,
    get_list_bookings,
    get_target_versions,
    json_error,
    serialize_booking,
)
from ..models import CurrentDeploymentState
from ..services.booking_service import BookingService
from ..services.deployment_request_service import DeploymentRequestService
from ..services.environment_access_service import EnvironmentAccessService


@main_bp.route("/api/bookings", methods=["GET"])
@login_required
def api_list_bookings():
    return jsonify(get_list_bookings(user=current_user()))


@main_bp.route("/api/bookings/export", methods=["GET"])
@login_required
def api_export_bookings():
    user = current_user()
    items = get_list_bookings(user=user)
    filtered_items = filter_bookings_for_history(
        items,
        env_type=request.args.get("env_type"),
        booking_type=request.args.get("booking_type"),
        status=request.args.get("status"),
        search=request.args.get("search"),
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "booking_id",
        "owner",
        "requested_by",
        "team",
        "environment_id",
        "environment_type",
        "booking_type",
        "status",
        "status_label",
        "start_time_utc",
        "end_time_utc",
        "description",
    ])
    for item in filtered_items:
        deployment = item.get("deployment_request") or {}
        writer.writerow([
            item.get("booking_id") or "",
            item.get("requested_by_name") or item.get("requested_by") or "",
            item.get("requested_by") or "",
            item.get("requested_by_team") or "",
            item.get("env_id") or "",
            deployment.get("requested_env_type") or "",
            item.get("booking_type") or "",
            item.get("lifecycle_status") or "",
            item.get("status_label") or "",
            item.get("start_time") or "",
            item.get("end_time") or "",
            item.get("description") or "",
        ])

    filename = "booking-history-{}.csv".format(datetime.utcnow().strftime("%Y%m%d-%H%M%S"))
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="{}"'.format(filename),
        },
    )


@main_bp.route("/api/bookings", methods=["POST"])
@login_required
def api_create_booking():
    user = current_user()
    data = request.get_json(silent=True) or {}
    booking, error, status_code = BookingService.create(data, user)
    if error:
        return json_error(error, status_code)

    response = jsonify(
        {
            "message": "Booking created successfully.",
            "booking_id": booking.booking_id,
            "booking": serialize_booking(booking),
        }
    )
    response.status_code = status_code
    return response


@main_bp.route("/api/bookings/<booking_id>", methods=["PUT"])
@login_required
def api_update_booking(booking_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    booking, error, status_code = BookingService.update(booking_id, data, user)
    if error:
        return json_error(error, status_code)
    return jsonify(
        {
            "message": "Booking updated successfully.",
            "booking": serialize_booking(booking),
        }
    )


@main_bp.route("/api/bookings/<booking_id>", methods=["DELETE"])
@login_required
def api_delete_booking(booking_id):
    user = current_user()
    booking, error, status_code = BookingService.delete(booking_id, user)
    if error:
        return json_error(error, status_code)
    return jsonify(
        {
            "message": "Booking cancelled successfully.",
            "booking": serialize_booking(booking),
        }
    )


@main_bp.route("/api/component-versions")
@login_required
def api_component_versions():
    target_key = request.args.get("target_key")
    package_key = request.args.get("package_key")
    return jsonify({"versions": get_target_versions(target_key, package_key=package_key)})


@main_bp.route("/api/environments")
@login_required
def api_environments():
    return jsonify({"environments": get_environments(user=current_user())})


@main_bp.route("/api/environment-types")
@login_required
def api_environment_types():
    return jsonify({"environment_types": get_environment_types()})


@main_bp.route("/api/deployment-requests", methods=["GET"])
@login_required
def api_list_deployment_requests():
    user = current_user()
    scope = request.args.get("scope", "auto")
    status = request.args.get("status")
    requests_data, error, status_code = DeploymentRequestService.list_requests(
        user,
        scope=scope,
        status=status,
    )
    if error:
        return json_error(error, status_code)
    return jsonify({"deployment_requests": requests_data})


@main_bp.route("/api/environment-operations", methods=["GET"])
@login_required
def api_environment_operations():
    user = current_user()
    operations, error, status_code = list_environment_operations(user)
    if error:
        return json_error(error, status_code)
    return jsonify({"operations": operations})


@main_bp.route("/api/deployment-requests", methods=["POST"])
@login_required
def api_create_deployment_request():
    user = current_user()
    data = request.get_json(silent=True) or {}
    deployment_request, error, status_code = DeploymentRequestService.create(data, user)
    if error:
        return json_error(error, status_code)
    response = jsonify(
        {
            "message": "Deployment request created successfully.",
            "deployment_request": DeploymentRequestService.serialize(
                deployment_request,
                user=user,
            ),
        }
    )
    response.status_code = status_code
    return response


@main_bp.route("/api/current-deployments", methods=["GET"])
@login_required
def api_list_current_deployments():
    query = CurrentDeploymentState.query.order_by(CurrentDeploymentState.updated_at.desc())
    env_scope_type = (request.args.get("env_scope_type") or "").strip().upper()
    env_id = (request.args.get("env_id") or "").strip()
    env_type = (request.args.get("env_type") or "").strip().upper()
    target_key = (request.args.get("target_key") or "").strip().upper()

    if env_scope_type:
        query = query.filter(CurrentDeploymentState.env_scope_type == env_scope_type)
    if env_id:
        query = query.filter(CurrentDeploymentState.env_id == env_id)
    if env_type:
        query = query.filter(CurrentDeploymentState.env_type == env_type)
    if target_key:
        query = query.filter(CurrentDeploymentState.target_key == target_key)

    return jsonify({
        "current_deployments": [item.to_dict() for item in query.all()],
    })


@main_bp.route("/api/deployment-requests/<deployment_request_id>/actions", methods=["POST"])
@login_required
def api_apply_deployment_request_action(deployment_request_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    deployment_request, error, status_code = DeploymentRequestService.apply_action(
        deployment_request_id,
        data.get("action"),
        user,
        payload=data,
    )
    if error:
        return json_error(error, status_code)
    return jsonify(
        {
            "message": "Deployment request updated successfully.",
            "deployment_request": DeploymentRequestService.serialize(
                deployment_request,
                user=user,
            ),
        }
    )


@main_bp.route("/api/deployment-requests/<deployment_request_id>/logs", methods=["GET"])
@login_required
def api_deployment_request_logs(deployment_request_id):
    user = current_user()
    requests_data, error, status_code = DeploymentRequestService.list_requests(
        user,
        scope="env" if can_access_env_team_screen(user) else "mine",
    )
    if error:
        return json_error(error, status_code)
    deployment_request = next(
        (
            item for item in requests_data
            if item["deployment_request_id"] == str(deployment_request_id)
        ),
        None,
    )
    if deployment_request is None:
        return json_error("Deployment request not found.", 404)
    return jsonify({"deployments": deployment_request.get("deployments", [])})


@main_bp.route("/api/environment-health/<env_id>/logs", methods=["GET"])
@login_required
def api_environment_health_logs(env_id):
    _ = env_id
    return json_error("Feature is not available yet.", 501)


@main_bp.route("/api/environment-health/<env_id>/auto-remediate", methods=["POST"])
@login_required
def api_environment_health_auto_remediate(env_id):
    _ = env_id
    return json_error("Feature is not available yet.", 501)


@main_bp.route("/api/environment-access/session", methods=["POST"])
@login_required
def api_create_environment_access_session():
    user = current_user()
    data = request.get_json(silent=True) or {}
    env_id = (data.get("env_id") or "").strip()
    access_type = (data.get("access_type") or "").strip()

    if not env_id:
        return json_error("env_id is required.", 400)
    if not access_type:
        return json_error("access_type is required.", 400)

    session_data, error = EnvironmentAccessService.start_terminal_session(
        env_id,
        access_type,
        user=user,
        request_host=request.host,
    )
    if error:
        return json_error(error, 400)

    return jsonify(session_data)


@main_bp.route("/api/environment-access/session/close", methods=["POST"])
@login_required
def api_close_environment_access_session():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()

    closed, error = EnvironmentAccessService.close_terminal_session(session_id)
    if error:
        return json_error(error, 400 if session_id else 422)

    return jsonify({"closed": bool(closed), "session_id": session_id})


@main_bp.route("/api/environment-access/link", methods=["POST"])
@login_required
def api_get_environment_access_link():
    data = request.get_json(silent=True) or {}
    env_id = (data.get("env_id") or "").strip()
    access_type = (data.get("access_type") or "").strip()

    if not env_id:
        return json_error("env_id is required.", 400)
    if not access_type:
        return json_error("access_type is required.", 400)

    link_data, error = EnvironmentAccessService.get_pay_ui_link(env_id, access_type)
    if error:
        return json_error(error, 400)

    return jsonify(link_data)
