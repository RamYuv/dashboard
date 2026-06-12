import unittest

from monitoring.services.status_fetcher import (
    REMOTE_EXECUTION_FAILED_OUTPUT,
    VmStatusFetcher,
)


class DummyExecutor:
    def run(self, host, username, password, command):
        raise AssertionError("Executor should not be used in parse_output tests.")


class VmStatusFetcherParseTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = VmStatusFetcher(executor=DummyExecutor())

    def test_green_when_service_installed_and_all_apps_running(self):
        parsed = self.fetcher.parse_output(
            """
app1: Running (pid:1234)
app2: Running (pid:5678)
""".strip()
        )
        self.assertEqual(parsed["vm_color"], "Green")
        self.assertEqual(parsed["component_data"]["app1"]["run_status"], "Running")
        self.assertEqual(parsed["component_data"]["app2"]["run_status"], "Running")

    def test_yellow_when_service_installed_but_no_apps_running(self):
        parsed = self.fetcher.parse_output("No apps are running")
        self.assertEqual(parsed["vm_color"], "Yellow")
        self.assertEqual(parsed["component_data"], {})

    def test_red_when_one_or_more_apps_are_not_running(self):
        parsed = self.fetcher.parse_output(
            """
app1: Running (pid:1234)
app2: NotRunning
""".strip()
        )
        self.assertEqual(parsed["vm_color"], "Red")
        self.assertEqual(parsed["component_data"]["app2"]["run_status"], "NotRunning")

    def test_black_when_command_not_found(self):
        parsed = self.fetcher.parse_output("/bin/sh: tcsexec: command not found")
        self.assertEqual(parsed["vm_color"], "Black")
        self.assertEqual(parsed["component_data"], {})

    def test_black_when_remote_execution_fails(self):
        parsed = self.fetcher.parse_output(REMOTE_EXECUTION_FAILED_OUTPUT)
        self.assertEqual(parsed["vm_color"], "Black")
        self.assertEqual(parsed["component_data"], {})

    def test_black_when_output_is_unparseable_and_not_idle(self):
        parsed = self.fetcher.parse_output("unexpected output from status command")
        self.assertEqual(parsed["vm_color"], "Black")
        self.assertEqual(parsed["component_data"], {})


if __name__ == "__main__":
    unittest.main()
