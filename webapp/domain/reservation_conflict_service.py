"""
Shared conflict checks between environment bookings and deployment requests.
"""

from flask import current_app, has_app_context

from ..helpers import build_deployment_request_window, to_utc_naive
from ..models import DeploymentRequest, EnvironmentBooking


BLOCKING_DEPLOYMENT_REQUEST_STATUSES = {
    "OPEN",
    "READY_FOR_DEPLOYMENT",
    "AUTO_DEPLOYMENT_RUNNING",
    "MANUAL_DEPLOYMENT_IN_PROGRESS",
}


class ReservationConflictService:
    """Check whether bookings and deployment requests can share an environment window."""

    @staticmethod
    def is_enabled():
        if not has_app_context():
            return False
        return bool(current_app.config.get("MUTUAL_ENV_RESERVATION_ENABLED", False))

    @staticmethod
    def overlaps(start_a, end_a, start_b, end_b):
        if not start_a or not end_a or not start_b or not end_b:
            return False
        return start_a < end_b and end_a > start_b

    @staticmethod
    def find_conflicting_booking(env_id, start_time, end_time, exclude_booking_id=None):
        query = EnvironmentBooking.query.filter(EnvironmentBooking.env_id == env_id)
        if exclude_booking_id is not None:
            query = query.filter(EnvironmentBooking.booking_id != str(exclude_booking_id))

        requested_start = to_utc_naive(start_time)
        requested_end = to_utc_naive(end_time)
        for booking in query.all():
            if booking.is_cancelled():
                continue
            if ReservationConflictService.overlaps(
                requested_start,
                requested_end,
                booking.start_time,
                booking.end_time,
            ):
                return booking
        return None

    @staticmethod
    def find_conflicting_deployment_request(
        env_id,
        start_time,
        end_time,
        exclude_deployment_request_id=None,
    ):
        query = DeploymentRequest.query.filter(
            DeploymentRequest.env_scope_type == "ENV",
            DeploymentRequest.env_id == env_id,
        )
        if exclude_deployment_request_id is not None:
            query = query.filter(
                DeploymentRequest.deployment_request_id != str(exclude_deployment_request_id)
            )

        requested_start = to_utc_naive(start_time)
        requested_end = to_utc_naive(end_time)
        for deployment_request in query.all():
            if deployment_request.status not in BLOCKING_DEPLOYMENT_REQUEST_STATUSES:
                continue
            deployment_start, deployment_end = build_deployment_request_window(
                deployment_request.planned_start_time
            )
            if ReservationConflictService.overlaps(
                requested_start,
                requested_end,
                deployment_start,
                deployment_end,
            ):
                return deployment_request
        return None

    @staticmethod
    def get_deployment_window(deployment_request):
        return build_deployment_request_window(deployment_request.planned_start_time)

    @staticmethod
    def get_deployment_window_for_start(planned_start_time):
        return build_deployment_request_window(planned_start_time)
