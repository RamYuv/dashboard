import unittest
from unittest.mock import MagicMock, patch

from monitoring.services.version_fetcher import VersionFetcher
from monitoring.version_pull_worker import VersionPullWorker


class VersionPullWorkerLookupTests(unittest.TestCase):
    def setUp(self):
        self.worker = VersionPullWorker(app=None, version_fetcher=None)

    def test_build_package_lookup_maps_package_key_and_name(self):
        target_def = {
            "packages": {
                "core": {"package_name": "Core Service", "server_type_key": "core"},
                "gateway": {"package_name": "Gateway Service", "server_type_key": "gateway"},
            }
        }
        lookup, packages = self.worker._build_package_lookup(target_def)
        self.assertEqual(lookup["core"], "core")
        self.assertEqual(lookup["Core Service"], "core")
        self.assertEqual(lookup["gateway"], "gateway")
        self.assertEqual(lookup["Gateway Service"], "gateway")
        self.assertEqual(lookup["core"], "core")
        self.assertEqual(packages, target_def["packages"])

    def test_build_package_lookup_does_not_ambiguously_map_server_type(self):
        target_def = {
            "packages": {
                "tool1": {"package_name": "Tool 1", "server_type_key": "tools"},
                "tool2": {"package_name": "Tool 2", "server_type_key": "tools"},
            }
        }
        lookup, _ = self.worker._build_package_lookup(target_def)
        self.assertEqual(lookup["tool1"], "tool1")
        self.assertEqual(lookup["tool2"], "tool2")
        self.assertNotIn("tools", lookup)

    def test_build_package_lookup_maps_unique_server_type(self):
        target_def = {
            "packages": {
                "db": {"package_name": "Database", "server_type_key": "db"},
            }
        }
        lookup, _ = self.worker._build_package_lookup(target_def)
        self.assertEqual(lookup["db"], "db")
        self.assertEqual(lookup["Database"], "db")
        self.assertEqual(lookup["db"], "db")

    def test_build_package_lookup_adds_case_insensitive_server_type_aliases(self):
        target_def = {
            "packages": {
                "gatway": {"package_name": "tcs_service_gatway", "server_type_key": "Getway"},
            }
        }
        lookup, _ = self.worker._build_package_lookup(target_def)
        self.assertEqual(lookup["Getway"], "gatway")
        self.assertEqual(lookup["getway"], "gatway")


class VersionFetcherTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = VersionFetcher(executor=MagicMock())

    def test_parse_output_prefers_patch_version_from_deploy_info(self):
        output = """
[Deploy Info]
env_name = DEV01
server = gateway
install_user = pali
deploy_service = DOM
mode = RT
versions = tcs_service-1.1.2.3_Patch1_20260604 tcs_service-1.1.2.3_20260604
"""
        parsed = self.fetcher.parse_output(output)
        self.assertEqual(
            parsed["versions"],
            {"gateway": "tcs_service-1.1.2.3_Patch1_20260604"},
        )
        self.assertEqual(
            parsed["deployment_details"],
            {"mode": "RT", "service_types": ["DOM"]},
        )
        self.assertIn("versions =", parsed["raw_output"])

    def test_parse_output_uses_single_version_from_deploy_info(self):
        output = """
[Deploy Info]
env_name = DEV01
server = gateway
install_user = pali
deploy_service = DOM
mode = RT
versions = tcs_service-1.1.2.3_20260604
"""
        parsed = self.fetcher.parse_output(output)
        self.assertEqual(
            parsed["versions"],
            {"gateway": "tcs_service-1.1.2.3_20260604"},
        )
        self.assertEqual(
            parsed["deployment_details"],
            {"mode": "RT", "service_types": ["DOM"]},
        )


class RunVersionPullTests(unittest.TestCase):
    @patch("monitoring.run_version_pull.create_monitoring_app")
    def test_run_once_uses_container_version_worker(self, create_monitoring_app):
        fake_worker = MagicMock()
        fake_worker.refresh.return_value = {"created": 1}
        fake_app = MagicMock()
        fake_ctx = MagicMock()
        fake_ctx.__enter__.return_value = fake_ctx
        fake_ctx.__exit__.return_value = None
        fake_app.app_context.return_value = fake_ctx
        fake_app.container.version_worker = fake_worker
        create_monitoring_app.return_value = fake_app

        from monitoring.run_version_pull import run_once

        result = run_once()

        fake_worker.refresh.assert_called_once()
        self.assertEqual(result, {"created": 1})


if __name__ == '__main__':
    unittest.main()
