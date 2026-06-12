"""
Booking service for managing environment reservations.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app

from ..models import (
    EnvironmentBooking,
    Environment,
    db,
)
from ..constants import VALID_BOOKING_TYPES, BOOKING_STATUS
from ..helpers import can_user_access_environment, to_utc_naive
from ..domain.reservation_conflict_service import ReservationConflictService
from .email_service import EmailDeliveryError, SendmailEmailService

logger = logging.getLogger(__name__)


class BookingValidator:
    """Validates booking data and constraints."""

    REQUIRED_FIELDS = ["env_id", "start_time", "end_time", "booking_type"]
    @staticmethod
    def validate_payload(data, user):
        """Validate booking payload and return error message if invalid."""
        # Check required fields
        for field in BookingValidator.REQUIRED_FIELDS:
            if not data.get(field):
                return f"{field} is required."

        # Validate booking type
        if data["booking_type"] not in VALID_BOOKING_TYPES:
            return "Invalid booking type."

        # Validate environment exists
        env = Environment.query.filter_by(env_id=data["env_id"]).first()
        if env is None:
            return "Invalid environment."
        if not can_user_access_environment(user, env):
            return "You can only book environments assigned to your team."

        # Validate datetime format
        try:
            start_time = to_utc_naive(data["start_time"])
            end_time = to_utc_naive(data["end_time"])
        except ValueError:
            return "Invalid date/time format."

        # Validate time range
        if start_time >= end_time:
            return "End time must be after start time."

        if data["booking_type"] != "RESERVATION":
            return "Only reservation bookings are supported here."

        return None


class BookingConflictChecker:
    """Checks for booking conflicts."""

    @staticmethod
    def find_conflict(env_id, start_time, end_time, exclude_booking_id=None):
        """Return the conflicting booking if one exists."""
        return ReservationConflictService.find_conflicting_booking(
            env_id,
            start_time,
            end_time,
            exclude_booking_id=exclude_booking_id,
        )

class BookingService:
    """Service for managing booking operations."""

    @staticmethod
    def _resolve_display_timezone(booking):
        timezone_name = (booking.user_timezone or "").strip() or "UTC"
        try:
            return ZoneInfo(timezone_name), timezone_name
        except Exception:
            return ZoneInfo("UTC"), "UTC"

    @staticmethod
    def _format_booking_time(booking_time, booking):
        timezone_info, timezone_name = BookingService._resolve_display_timezone(booking)
        utc_value = booking_time.replace(tzinfo=ZoneInfo("UTC"))
        local_value = utc_value.astimezone(timezone_info)
        return "{} ({})".format(local_value.strftime("%Y-%m-%d %H:%M"), timezone_name)

    @staticmethod
    def _send_booking_confirmation(booking):
        requester = booking.requester
        recipient = (requester.email_id or "").strip() if requester and requester.email_id else ""
        if not recipient:
            current_app.logger.warning(
                "Skipping booking confirmation for %s because requester email is unavailable.",
                booking.booking_id,
            )
            return

        subject = "[EnvBooking] Booking confirmed {}".format(booking.booking_id)
        body = "\n".join([
            "Your environment booking has been created successfully.",
            "",
            "Booking ID: {}".format(booking.booking_id),
            "Environment: {}".format(booking.env_id),
            "Requested by: {}".format(
                requester.full_name if requester and requester.full_name else booking.requested_by
            ),
            "User ID: {}".format(booking.requested_by),
            "Booking Type: {}".format(booking.booking_type),
            "Status: {}".format(booking.status),
            "Start: {}".format(BookingService._format_booking_time(booking.start_time, booking)),
            "End: {}".format(BookingService._format_booking_time(booking.end_time, booking)),
            "Description: {}".format(booking.description or "Not provided"),
            "",
            "Timezone used for display: {}".format(
                BookingService._resolve_display_timezone(booking)[1]
            ),
        ])

        try:
            SendmailEmailService.send_message(
                subject=subject,
                recipients=[recipient],
                body=body,
                reply_to=recipient,
            )
            current_app.logger.info(
                "Booking confirmation sent for %s to %s",
                booking.booking_id,
                recipient,
            )
        except EmailDeliveryError as exc:
            current_app.logger.exception(
                "Failed to send booking confirmation for %s: %s",
                booking.booking_id,
                exc,
            )

    @staticmethod
    def _build_conflict_message(booking):
        return (
            "This environment is already booked. "
            "Conflict with booking {0} from {1} to {2} UTC."
        ).format(
            booking.booking_id,
            booking.start_time.strftime("%d %b %Y %H:%M"),
            booking.end_time.strftime("%d %b %Y %H:%M"),
        )

    @staticmethod
    def _build_deployment_conflict_message(deployment_request):
        planned_start = deployment_request.planned_start_time
        _, planned_end = ReservationConflictService.get_deployment_window(deployment_request)
        return (
            "This environment already has a deployment reservation. "
            "Conflict with deployment request {0} from {1} to {2} UTC."
        ).format(
            deployment_request.deployment_request_id,
            planned_start.strftime("%d %b %Y %H:%M") if planned_start else "unknown",
            planned_end.strftime("%d %b %Y %H:%M") if planned_end else "unknown",
        )

    @staticmethod
    def create(data, user):
        """Create a new booking."""
        validation_error = BookingValidator.validate_payload(data, user)
        if validation_error:
            logger.warning(
                "Booking creation rejected for user %s: %s",
                user.username,
                validation_error,
            )
            return None, validation_error, 400

        conflict_booking = BookingConflictChecker.find_conflict(
            data["env_id"], data["start_time"], data["end_time"]
        )
        if conflict_booking is not None:
            logger.warning(
                "Booking conflict for user %s on env %s with booking %s",
                user.username,
                data["env_id"],
                conflict_booking.booking_id,
            )
            return (
                None,
                BookingService._build_conflict_message(conflict_booking),
                409,
            )

        if ReservationConflictService.is_enabled():
            conflicting_deployment_request = (
                ReservationConflictService.find_conflicting_deployment_request(
                    data["env_id"],
                    data["start_time"],
                    data["end_time"],
                )
            )
            if conflicting_deployment_request is not None:
                logger.warning(
                    "Booking conflict for user %s on env %s with deployment request %s",
                    user.username,
                    data["env_id"],
                    conflicting_deployment_request.deployment_request_id,
                )
                return (
                    None,
                    BookingService._build_deployment_conflict_message(
                        conflicting_deployment_request
                    ),
                    409,
                )

        environment = Environment.query.filter_by(env_id=data["env_id"]).first()
        booking = EnvironmentBooking(
            environment=environment,
            requester=user,
            start_time=to_utc_naive(data["start_time"]),
            end_time=to_utc_naive(data["end_time"]),
            booking_type=data["booking_type"],
            description=data.get("description"),
            user_timezone=data.get("user_timezone"),
            status="scheduled",
        )
        db.session.add(booking)
        db.session.flush()

        db.session.commit()
        BookingService._send_booking_confirmation(booking)
        logger.info(
            "Booking %s created by user %s for env %s",
            booking.booking_id,
            user.username,
            booking.env_id,
        )
        return booking, None, 201

    @staticmethod
    def update(booking_id, data, user):
        """Update an existing booking."""
        booking = EnvironmentBooking.query.get(str(booking_id))
        if booking is None:
            logger.warning("Booking update failed because booking %s was not found.", booking_id)
            return None, "Booking not found.", 404

        if booking.requested_by != user.username and user.role != "admin":
            logger.warning(
                "Booking update denied for user %s on booking %s",
                user.username,
                booking_id,
            )
            return None, "You can only update your own bookings.", 403

        if not booking.is_mutable():
            logger.warning(
                "Booking update rejected for booking %s because it is not editable in its current lifecycle state.",
                booking_id,
            )
            return None, "Only scheduled bookings can be updated.", 400

        validation_error = BookingValidator.validate_payload(data, user)
        if validation_error:
            logger.warning(
                "Booking update rejected for booking %s by user %s: %s",
                booking_id,
                user.username,
                validation_error,
            )
            return None, validation_error, 400

        conflict_booking = BookingConflictChecker.find_conflict(
            data["env_id"], data["start_time"], data["end_time"], booking_id
        )
        if conflict_booking is not None:
            logger.warning(
                "Booking update conflict for booking %s with booking %s",
                booking_id,
                conflict_booking.booking_id,
            )
            return (
                None,
                BookingService._build_conflict_message(conflict_booking),
                409,
            )

        if ReservationConflictService.is_enabled():
            conflicting_deployment_request = (
                ReservationConflictService.find_conflicting_deployment_request(
                    data["env_id"],
                    data["start_time"],
                    data["end_time"],
                )
            )
            if conflicting_deployment_request is not None:
                logger.warning(
                    "Booking update conflict for booking %s with deployment request %s",
                    booking_id,
                    conflicting_deployment_request.deployment_request_id,
                )
                return (
                    None,
                    BookingService._build_deployment_conflict_message(
                        conflicting_deployment_request
                    ),
                    409,
                )

        booking.environment = Environment.query.filter_by(
            env_id=data["env_id"]
        ).first()
        booking.start_time = to_utc_naive(data["start_time"])
        booking.end_time = to_utc_naive(data["end_time"])
        booking.booking_type = data["booking_type"]
        booking.description = data.get("description")
        booking.user_timezone = data.get("user_timezone")
        booking.updated_at = datetime.utcnow()

        db.session.commit()
        logger.info("Booking %s updated by user %s", booking.booking_id, user.username)
        return booking, None, 200

    @staticmethod
    def delete(booking_id, user):
        """Delete (cancel) a booking."""
        booking = EnvironmentBooking.query.get(str(booking_id))
        if booking is None:
            logger.warning("Booking cancellation failed because booking %s was not found.", booking_id)
            return None, "Booking not found.", 404

        if booking.requested_by != user.username and user.role != "admin":
            logger.warning(
                "Booking cancellation denied for user %s on booking %s",
                user.username,
                booking_id,
            )
            return None, "You can only cancel your own bookings.", 403

        if not booking.is_mutable():
            logger.warning(
                "Booking cancellation rejected for booking %s because it is not editable in its current lifecycle state.",
                booking_id,
            )
            return None, "Only scheduled bookings can be cancelled.", 400

        booking.status = BOOKING_STATUS["CANCELLED"]
        booking.updated_at = datetime.utcnow()
        db.session.commit()
        logger.info("Booking %s cancelled by user %s", booking.booking_id, user.username)
        return booking, None, 200
