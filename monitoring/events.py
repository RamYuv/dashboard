"""Small in-memory event buffer for monitoring refresh events.

This is mainly useful for debugging and future extension points. It is not part
of the booking flow and does not persist across process restarts.
"""

class EventBroker:
    """Keep a small rolling list of recent monitoring events."""

    def __init__(self):
        self._events = []

    def publish(self, event_name, payload):
        event = {"event": event_name, "payload": payload}
        self._events.append(event)
        self._events = self._events[-50:]
        return event

    def recent_events(self):
        return list(self._events)
