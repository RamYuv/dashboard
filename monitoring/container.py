"""Dependency container for monitoring components.

This module wires together the collaborating monitoring objects used by both
the web app and the monitoring worker entrypoint.
"""

class AppContainer:
    """Build and expose monitoring collaborators in one place."""

    def __init__(self, app, monitor_state):
        from monitoring.events import EventBroker
        from monitoring.services.remote_executor import FabricRemoteExecutor
        from monitoring.services.status_aggregator import EnvStatusAggregator
        from monitoring.services.status_fetcher import VmStatusFetcher
        from monitoring.worker import EnvMonitorWorker

        self.app = app
        self.monitor_state = monitor_state
        self.event_broker = EventBroker()
        self.remote_executor = FabricRemoteExecutor()
        self.vm_status_fetcher = VmStatusFetcher(executor=self.remote_executor)
        self.env_status_aggregator = EnvStatusAggregator()

        self.env_worker = EnvMonitorWorker(
            app=self.app,
            environments=[],
            monitor_state=self.monitor_state,
            event_broker=self.event_broker,
            status_fetcher=self.vm_status_fetcher,
            status_aggregator=self.env_status_aggregator,
        )
