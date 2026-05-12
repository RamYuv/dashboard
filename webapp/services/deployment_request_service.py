"""
Service layer for standalone deployment requests.
"""

from datetime import datetime

from flask import current_app

from ..auto_deployment_service import AutoDeploymentError, AutoDeploymentService
from ..auth_service import can_access_env_team_screen
from ..domain.deployment_targets import (
    get_selected_package_keys,
    get_target_definition,
    packages_support_scope,
    resolve_request_targets,
    target_supports_multiple_packages,
    target_supports_scope,
)
from .email_service import EmailDeliveryError, SendmailEmailService
from ..helpers import to_utc_naive
from ..models import (
    ComponentBuild,
    CurrentDeploymentState,
    Deployment,
    DeploymentRequest,
    Environment,
    Team,
    TeamMember,
    User,
    db,
)
from ..domain.reservation_conflict_service import ReservationConflictService


DEPLOYMENT_REQUEST_STATUSES = {
    "OPEN": "OPEN",
    "READY_FOR_DEPLOYMENT": "READY_FOR_DEPLOYMENT",
    "AUTO_DEPLOYMENT_RUNNING": "AUTO_DEPLOYMENT_RUNNING",
    "MANUAL_DEPLOYMENT_IN_PROGRESS": "MANUAL_DEPLOYMENT_IN_PROGRESS",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "REJECTED": "REJECTED",
}


class DeploymentRequestService:
    """Create, list, and progress deployment requests."""

    @staticmethod
    def _build_booking_conflict_message(booking):
        return (
            "This environment already has a booking reservation. "
            "Conflict with booking {0} from {1} to {2} UTC."
        ).format(
            booking.booking_id,
            booking.start_time.strftime("%d %b %Y %H:%M"),
            booking.end_time.strftime("%d %b %Y %H:%M"),
        )

    @staticmethod
    def _describe_missing_mappings(env_id, requested_env_type, resolved_targets):
        missing_targets = [
            target for target in resolved_targets
            if not target.get("environment_host_mapping_id")
        ]
        if not missing_targets:
            return None

        scope_label = env_id or requested_env_type or "the selected scope"
        missing_descriptions = []
        for target in missing_targets:
            resolution_error = target.get("resolution_error")
            missing_descriptions.append(
                "{} ({}){}".format(
                    target.get("package_name") or target.get("package_key") or "unknown package",
                    target.get("server_role_key") or "unknown server role",
                    ": {}".format(resolution_error) if resolution_error else "",
                )
            )
        return (
            "No deployment host mapping was found for {}. "
            "Missing package/server-role mappings: {}."
        ).format(scope_label, ", ".join(missing_descriptions))

    @staticmethod
    def _normalize_service_types(target_key, deployment_data):
        if target_key != "TCS_APP":
            return []

        service_types = deployment_data.get("service_types") or []
        if isinstance(service_types, str):
            service_types = [service_types]

        normalized = []
        for service_type in service_types:
            value = (service_type or "").strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def _resolve_build_name(target_key, target_definition, deployment_data, selected_package_keys):
        packages = target_definition.get("packages") or {}
        if target_key == "TOOLS" and selected_package_keys:
            selected_package = packages.get(selected_package_keys[0]) or {}
            return (
                deployment_data.get("artifact_name") or
                selected_package.get("package_name") or
                selected_package_keys[0]
            )
        return (
            deployment_data.get("artifact_name") or
            target_key
        )

    @staticmethod
    def _find_or_create_build(target_key, target_definition, deployment_data, selected_package_keys):
        build_name = DeploymentRequestService._resolve_build_name(
            target_key,
            target_definition,
            deployment_data,
            selected_package_keys,
        )
        requested_version = deployment_data.get("requested_version")
        build = ComponentBuild.query.filter_by(
            target_key=target_key,
            build_name=build_name,
            version=requested_version,
        ).first()
        if build is not None:
            return build

        build = ComponentBuild(
            target_key=target_key,
            build_name=build_name,
            version=requested_version,
            artifact_name=build_name,
        )
        db.session.add(build)
        db.session.flush()
        return build

    @staticmethod
    def _available_actions(deployment_request, user):
        if deployment_request is None:
            return []

        actions = []
        status = deployment_request.status
        is_env_user = can_access_env_team_screen(user)

        if is_env_user and status == DEPLOYMENT_REQUEST_STATUSES["OPEN"]:
            actions.extend(["approve", "reject"])
        if is_env_user and status == DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]:
            actions.extend(["auto_deploy", "manual_deploy", "cancel"])
        if is_env_user and status == DEPLOYMENT_REQUEST_STATUSES["AUTO_DEPLOYMENT_RUNNING"]:
            actions.extend(["view_logs", "mark_failed", "mark_completed"])
        if is_env_user and status == DEPLOYMENT_REQUEST_STATUSES["MANUAL_DEPLOYMENT_IN_PROGRESS"]:
            actions.extend(["mark_completed", "mark_failed"])
        if is_env_user and status == DEPLOYMENT_REQUEST_STATUSES["FAILED"]:
            actions.extend(["view", "retry"])
        if is_env_user and status in {
            DEPLOYMENT_REQUEST_STATUSES["COMPLETED"],
            DEPLOYMENT_REQUEST_STATUSES["REJECTED"],
            DEPLOYMENT_REQUEST_STATUSES["CANCELLED"],
        }:
            actions.append("view")
        return actions

    @staticmethod
    def serialize(deployment_request, user=None):
        data = deployment_request.to_dict()
        data["available_actions"] = DeploymentRequestService._available_actions(
            deployment_request,
            user,
        )
        return data

    @staticmethod
    def list_requests(user, scope="auto", status=None):
        query = DeploymentRequest.query.order_by(
            DeploymentRequest.created_at.desc(),
            DeploymentRequest.planned_start_time.desc(),
        )
        normalized_scope = (scope or "auto").strip().lower()
        normalized_status = (status or "").strip().upper()

        if normalized_status:
            query = query.filter(DeploymentRequest.status == normalized_status)

        if normalized_scope == "mine":
            query = query.filter(DeploymentRequest.requested_by == user.username)
        elif normalized_scope == "env":
            if not can_access_env_team_screen(user):
                return [], "You do not have access to the ENV deployment dashboard.", 403
        elif normalized_scope == "all":
            if not can_access_env_team_screen(user):
                query = query.filter(DeploymentRequest.requested_by == user.username)
        else:
            if not can_access_env_team_screen(user):
                query = query.filter(DeploymentRequest.requested_by == user.username)

        requests = query.all()
        return [
            DeploymentRequestService.serialize(item, user=user)
            for item in requests
        ], None, 200

    @staticmethod
    def _validate_payload(data):
        try:
            planned_start_time = to_utc_naive(data.get("planned_start_time"))
        except ValueError:
            return "Invalid planned start time."

        if planned_start_time is None:
            return "Planned start time is required."

        deployment = data.get("deployment_request") or {}
        target_key = (deployment.get("target_key") or "").strip().upper()
        if not target_key:
            return "Deployment target is required."

        env_scope_type = (deployment.get("env_scope_type") or "ENV").strip().upper()
        env_id = (data.get("env_id") or "").strip()
        requested_env_type = (data.get("requested_env_type") or "").strip().upper()

        package_keys = get_selected_package_keys(target_key, deployment)
        if not package_keys:
            return "Target package is required."
        if not target_supports_multiple_packages(target_key) and len(package_keys) > 1:
            return "Deployment target '{}' allows only one package selection.".format(
                target_key
            )

        if not target_supports_scope(target_key, env_scope_type):
            return "Deployment target '{}' does not support {} scope.".format(
                target_key,
                env_scope_type,
            )

        if not packages_support_scope(target_key, package_keys, env_scope_type):
            return "One or more selected packages do not support {} scope.".format(
                env_scope_type
            )

        if env_scope_type == "ENV_TYPE":
            if not requested_env_type:
                return "Environment type is required for shared deployments."
        else:
            if not env_id:
                return "env_id is required."
            env = Environment.query.filter_by(env_id=env_id).first()
            if env is None:
                return "Invalid environment."
            if not requested_env_type:
                requested_env_type = (env.env_type or "").strip().upper()

        if not deployment.get("requested_version"):
            return "Build/version is required."
        if target_key == "TCS_APP" and not deployment.get("testing_mode"):
            return "Testing mode is required."

        return None

    @staticmethod
    def _resolve_request_scope(data, deployment_data):
        env_scope_type = (deployment_data.get("env_scope_type") or "ENV").strip().upper()
        env_id = (data.get("env_id") or "").strip() or None
        requested_env_type = (data.get("requested_env_type") or "").strip().upper() or None
        if env_id:
            env = Environment.query.filter_by(env_id=env_id).first()
            if env is not None and not requested_env_type:
                requested_env_type = (env.env_type or "").strip().upper() or requested_env_type
        return env_scope_type, env_id, requested_env_type

    @staticmethod
    def _env_notification_recipients():
        recipients = []
        configured = current_app.config.get("ENV_TEAM_EMAILS")
        if configured:
            recipients.extend([
                item.strip() for item in configured.split(",") if item.strip()
            ])

        team_users = (
            User.query.join(TeamMember, TeamMember.user_id == User.user_id)
            .join(Team, Team.team_id == TeamMember.team_id)
            .filter(Team.team_name == "env", User.email_id.isnot(None))
            .distinct()
            .all()
        )
        recipients.extend([user.email_id for user in team_users if user.email_id])
        unique = []
        for recipient in recipients:
            if recipient not in unique:
                unique.append(recipient)
        return unique

    @staticmethod
    def _notify_env_team(deployment_request):
        recipients = DeploymentRequestService._env_notification_recipients()
        if not recipients:
            current_app.logger.warning(
                "Skipping ENV team notification for deployment request %s because no recipients are configured.",
                deployment_request.deployment_request_id,
            )
            return

        requester = deployment_request.requester
        planned_start = (
            deployment_request.planned_start_time.strftime("%Y-%m-%d %H:%M UTC")
            if deployment_request.planned_start_time else
            "Not provided"
        )
        subject = "[EnvBooking] New deployment request {}".format(
            deployment_request.deployment_request_id
        )
        body = "\n".join([
            "A new deployment request has been raised for the ENV team.",
            "",
            "Request ID: {}".format(deployment_request.deployment_request_id),
            "Environment: {}".format(
                deployment_request.env_id
                if deployment_request.env_scope_type == "ENV"
                else deployment_request.requested_env_type or "Not provided"
            ),
            "Requested by: {}".format(
                requester.name if requester and requester.name else deployment_request.requested_by
            ),
            "Requester user ID: {}".format(deployment_request.requested_by),
            "Requester email: {}".format(
                requester.email_id if requester and requester.email_id else "Not available"
            ),
            "Target: {}".format(deployment_request.target_key),
            "Build: {}".format(deployment_request.build_name or "Not provided"),
            "Version: {}".format(deployment_request.requested_version or "Not provided"),
            "Planned start: {}".format(planned_start),
            "Jira ID: {}".format(deployment_request.jira_id or "Not provided"),
            "Description: {}".format(deployment_request.description or "Not provided"),
            "Remarks: {}".format(deployment_request.remarks or "Not provided"),
            "",
            "Status: {}".format(deployment_request.status),
        ])

        try:
            SendmailEmailService.send_message(
                subject=subject,
                recipients=recipients,
                body=body,
                reply_to=requester.email_id if requester and requester.email_id else None,
            )
            deployment_request.last_notified_at = datetime.utcnow()
            current_app.logger.info(
                "ENV team notification sent for deployment request %s to %s",
                deployment_request.deployment_request_id,
                recipients,
            )
        except EmailDeliveryError as exc:
            current_app.logger.exception(
                "Failed to send ENV team notification for deployment request %s: %s",
                deployment_request.deployment_request_id,
                exc,
            )

    @staticmethod
    def create(data, user):
        validation_error = DeploymentRequestService._validate_payload(data)
        if validation_error:
            return None, validation_error, 400

        deployment_data = data.get("deployment_request") or {}
        target_key = (deployment_data.get("target_key") or "").strip().upper()
        env_scope_type, env_id, requested_env_type = DeploymentRequestService._resolve_request_scope(
            data,
            deployment_data,
        )
        deployment_data["env_scope_type"] = env_scope_type
        deployment_data["requested_env_type"] = requested_env_type

        planned_start_time = to_utc_naive(data["planned_start_time"])
        if ReservationConflictService.is_enabled() and env_scope_type == "ENV" and env_id:
            _, planned_end_time = ReservationConflictService.get_deployment_window_for_start(
                planned_start_time
            )
            conflicting_booking = ReservationConflictService.find_conflicting_booking(
                env_id,
                planned_start_time,
                planned_end_time,
            )
            if conflicting_booking is not None:
                return (
                    None,
                    DeploymentRequestService._build_booking_conflict_message(
                        conflicting_booking
                    ),
                    409,
                )

        target_definition = get_target_definition(target_key) or {}
        selected_package_keys = get_selected_package_keys(target_key, deployment_data)
        build = DeploymentRequestService._find_or_create_build(
            target_key,
            target_definition,
            deployment_data,
            selected_package_keys,
        )
        resolved_targets = resolve_request_targets(env_id, deployment_data)
        if not any(
            target.get("environment_host_mapping_id")
            for target in resolved_targets
        ):
            return None, DeploymentRequestService._describe_missing_mappings(
                env_id,
                requested_env_type,
                resolved_targets,
            ) or "No deployment host mapping was found for the selected scope and package(s).", 400
        build_name = DeploymentRequestService._resolve_build_name(
            target_key,
            target_definition,
            deployment_data,
            selected_package_keys,
        )
        deployment_request = DeploymentRequest(
            env_id=env_id,
            requested_env_type=requested_env_type,
            env_scope_type=env_scope_type,
            requested_by=user.username,
            planned_start_time=planned_start_time,
            build_id=build.build_id if build is not None else None,
            target_key=target_key,
            requested_version=deployment_data.get("requested_version"),
            package_keys_raw="[]",
            testing_mode=deployment_data.get("testing_mode") if target_key == "TCS_APP" else "",
            jira_id=deployment_data.get("jira_id"),
            description=data.get("description"),
            remarks=deployment_data.get("remarks") or data.get("description"),
            status=DEPLOYMENT_REQUEST_STATUSES["OPEN"],
        )
        deployment_request.package_keys = selected_package_keys
        deployment_request.set_service_types(
            DeploymentRequestService._normalize_service_types(target_key, deployment_data)
        )
        db.session.add(deployment_request)
        db.session.flush()

        deployment_request.deployments = [
            Deployment(
                deployment_request_id=deployment_request.deployment_request_id,
                environment_host_mapping_id=target.get("environment_host_mapping_id"),
                package_key=target["package_key"],
                package_name=target.get("package_name") or target["package_key"],
                deployed_version=deployment_data.get("requested_version"),
                deployment_status="PENDING",
            )
            for target in resolved_targets
            if target.get("environment_host_mapping_id") is not None
        ]

        DeploymentRequestService._notify_env_team(deployment_request)
        db.session.commit()
        return deployment_request, None, 201

    @staticmethod
    def _update_current_deployment_state(deployment_request, user):
        for deployment in deployment_request.deployments:
            if deployment.deployment_status != "SUCCESS":
                continue
            mapping = deployment.environment_host_mapping
            if mapping is None:
                continue

            state = CurrentDeploymentState.query.filter_by(
                env_scope_type=deployment_request.env_scope_type,
                env_id=deployment_request.env_id,
                env_type=deployment_request.requested_env_type,
                environment_host_mapping_id=deployment.environment_host_mapping_id,
                package_key=deployment.package_key,
            ).first()
            if state is None:
                state = CurrentDeploymentState(
                    env_scope_type=deployment_request.env_scope_type,
                    env_id=deployment_request.env_id,
                    env_type=deployment_request.requested_env_type,
                    environment_host_mapping_id=deployment.environment_host_mapping_id,
                    package_key=deployment.package_key,
                )
                db.session.add(state)

            state.target_key = deployment_request.target_key
            state.package_name = deployment.package_name
            state.current_version = deployment.deployed_version
            state.source = "DEPLOYMENT"
            state.status = "CURRENT"
            state.updated_by = user.username if user else None
            state.deployment_request_id = deployment_request.deployment_request_id
            state.notes = None

    @staticmethod
    def _get_request_for_action(deployment_request_id):
        return DeploymentRequest.query.get(str(deployment_request_id))

    @staticmethod
    def _transition_to_ready(deployment_request, user):
        if deployment_request.status != DEPLOYMENT_REQUEST_STATUSES["OPEN"]:
            return "Only OPEN requests can be approved."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]
        deployment_request.approved_by = user.username
        deployment_request.approved_at = datetime.utcnow()
        deployment_request.failure_reason = None
        return None

    @staticmethod
    def _transition_to_rejected(deployment_request, payload):
        if deployment_request.status != DEPLOYMENT_REQUEST_STATUSES["OPEN"]:
            return "Only OPEN requests can be rejected."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["REJECTED"]
        deployment_request.failure_reason = payload.get("reason") or payload.get("remarks")
        deployment_request.completed_at = datetime.utcnow()
        return None

    @staticmethod
    def _transition_to_auto_running(deployment_request):
        if deployment_request.status != DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]:
            return "Only READY_FOR_DEPLOYMENT requests can start auto deployment."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["AUTO_DEPLOYMENT_RUNNING"]
        deployment_request.execution_mode = "AUTO"
        deployment_request.completed_at = None
        deployment_request.failure_reason = None
        for deployment in deployment_request.deployments:
            deployment.deployment_status = "RUNNING"
            deployment.started_at = datetime.utcnow()
            deployment.log_excerpt = "Auto deployment started."
        return None

    @staticmethod
    def _trigger_auto_deployment(deployment_request):
        try:
            launch_result = AutoDeploymentService.start(deployment_request)
        except AutoDeploymentError as exc:
            deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]
            deployment_request.execution_mode = None
            deployment_request.failure_reason = str(exc)
            for deployment in deployment_request.deployments:
                deployment.deployment_status = "PENDING"
                deployment.started_at = None
                deployment.log_excerpt = "Auto deployment trigger failed: {}".format(exc)
            return str(exc)

        log_path = launch_result.get("log_path")
        pid = launch_result.get("pid")
        for deployment in deployment_request.deployments:
            deployment.log_excerpt = "Auto deployment launched (pid={}, log={})".format(
                pid,
                log_path,
            )
        current_app.logger.info(
            "Launched auto deployment for request %s with pid=%s payload=%s",
            deployment_request.deployment_request_id,
            pid,
            launch_result.get("payload_path"),
        )
        return None

    @staticmethod
    def _transition_to_manual_running(deployment_request):
        if deployment_request.status != DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]:
            return "Only READY_FOR_DEPLOYMENT requests can start manual deployment."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["MANUAL_DEPLOYMENT_IN_PROGRESS"]
        deployment_request.execution_mode = "MANUAL"
        deployment_request.completed_at = None
        deployment_request.failure_reason = None
        for deployment in deployment_request.deployments:
            if deployment.deployment_status == "PENDING":
                deployment.deployment_status = "RUNNING"
                deployment.started_at = datetime.utcnow()
                deployment.log_excerpt = "Manual deployment in progress."
        return None

    @staticmethod
    def _mark_completed(deployment_request, user):
        if deployment_request.status not in {
            DEPLOYMENT_REQUEST_STATUSES["AUTO_DEPLOYMENT_RUNNING"],
            DEPLOYMENT_REQUEST_STATUSES["MANUAL_DEPLOYMENT_IN_PROGRESS"],
        }:
            return "Only in-progress deployments can be completed."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["COMPLETED"]
        deployment_request.completed_at = datetime.utcnow()
        deployment_request.failure_reason = None
        for deployment in deployment_request.deployments:
            deployment.deployment_status = "SUCCESS"
            deployment.completed_at = datetime.utcnow()
            if not deployment.log_excerpt:
                deployment.log_excerpt = "Deployment completed successfully."
        DeploymentRequestService._update_current_deployment_state(deployment_request, user)
        return None

    @staticmethod
    def _mark_failed(deployment_request, payload):
        if deployment_request.status not in {
            DEPLOYMENT_REQUEST_STATUSES["AUTO_DEPLOYMENT_RUNNING"],
            DEPLOYMENT_REQUEST_STATUSES["MANUAL_DEPLOYMENT_IN_PROGRESS"],
        }:
            return "Only in-progress deployments can be failed."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["FAILED"]
        deployment_request.completed_at = datetime.utcnow()
        deployment_request.failure_reason = payload.get("reason") or "Deployment failed."
        for deployment in deployment_request.deployments:
            if deployment.deployment_status in {"PENDING", "RUNNING"}:
                deployment.deployment_status = "FAILED"
                deployment.completed_at = datetime.utcnow()
                deployment.log_excerpt = deployment_request.failure_reason
        return None

    @staticmethod
    def _cancel(deployment_request, payload):
        if deployment_request.status != DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]:
            return "Only READY_FOR_DEPLOYMENT requests can be cancelled."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["CANCELLED"]
        deployment_request.completed_at = datetime.utcnow()
        deployment_request.failure_reason = payload.get("reason") or "Cancelled by ENV team."
        for deployment in deployment_request.deployments:
            deployment.deployment_status = "CANCELLED"
            deployment.completed_at = datetime.utcnow()
            deployment.log_excerpt = deployment_request.failure_reason
        return None

    @staticmethod
    def _retry(deployment_request):
        if deployment_request.status != DEPLOYMENT_REQUEST_STATUSES["FAILED"]:
            return "Only FAILED requests can be retried."
        deployment_request.status = DEPLOYMENT_REQUEST_STATUSES["READY_FOR_DEPLOYMENT"]
        deployment_request.execution_mode = None
        deployment_request.completed_at = None
        deployment_request.failure_reason = None
        for deployment in deployment_request.deployments:
            deployment.deployment_status = "PENDING"
            deployment.started_at = None
            deployment.completed_at = None
            deployment.log_excerpt = "Retry requested."
        return None

    @staticmethod
    def apply_action(deployment_request_id, action, user, payload=None):
        payload = payload or {}
        deployment_request = DeploymentRequestService._get_request_for_action(
            deployment_request_id
        )
        if deployment_request is None:
            return None, "Deployment request not found.", 404

        if not can_access_env_team_screen(user):
            return None, "You do not have access to perform ENV deployment actions.", 403

        action_name = (action or "").strip().lower()
        transitions = {
            "approve": lambda: DeploymentRequestService._transition_to_ready(deployment_request, user),
            "reject": lambda: DeploymentRequestService._transition_to_rejected(deployment_request, payload),
            "auto_deploy": lambda: DeploymentRequestService._transition_to_auto_running(deployment_request),
            "manual_deploy": lambda: DeploymentRequestService._transition_to_manual_running(deployment_request),
            "mark_completed": lambda: DeploymentRequestService._mark_completed(deployment_request, user),
            "mark_failed": lambda: DeploymentRequestService._mark_failed(deployment_request, payload),
            "cancel": lambda: DeploymentRequestService._cancel(deployment_request, payload),
            "retry": lambda: DeploymentRequestService._retry(deployment_request),
        }
        transition = transitions.get(action_name)
        if transition is None:
            return None, "Unsupported action.", 400

        error = transition()
        if error:
            return None, error, 400

        if action_name == "auto_deploy":
            error = DeploymentRequestService._trigger_auto_deployment(deployment_request)
            if error:
                return None, error, 400

        deployment_request.updated_at = datetime.utcnow()
        db.session.commit()
        return deployment_request, None, 200
