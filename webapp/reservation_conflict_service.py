"""Backward-compatible import wrapper for reservation conflict policy."""

from .domain.reservation_conflict_service import ReservationConflictService

__all__ = ["ReservationConflictService"]
