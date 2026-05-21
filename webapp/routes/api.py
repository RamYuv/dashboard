from flask import jsonify, request

from .blueprint import main_bp
from ..auth_service import can_access_env_team_screen, current_user, login_required
from ..helpers import (
    get_environment_types,
    get_environments,
    get_list_bookings,
    get_target_versions,
    json_error,
    serialize_booking,
)
from ..models import CurrentDeploymentState
from ..services.booking_service import BookingService
from ..services.deployment_request_service import DeploymentRequestService


@main_bp.route("/api/bookings", methods=["GET"])
@login_required
def api_list_bookings():
    return jsonify(get_list_bookings())


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
    return jsonify({"environments": get_environments()})


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
    return jsonify({"deployments": deployment_request.get("resolved_targets", [])})
