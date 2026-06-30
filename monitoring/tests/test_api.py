import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "api.py"
SPEC = importlib.util.spec_from_file_location("monitoring_api_under_test", MODULE_PATH)
monitoring_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitoring_api)


class MonitoringApiVersionDisplayTests(unittest.TestCase):
    def test_display_tcs_version_returns_full_version_when_all_match(self):
        version = "tcs_server-1.1.2.1_Patch2_20260623"
        result = monitoring_api._display_tcs_version([version, version])
        self.assertEqual(result, version)

    def test_display_tcs_version_returns_preferred_full_version_when_versions_differ(self):
        result = monitoring_api._display_tcs_version(
            [
                "tcs_server-1.1.2.1_Patch1_20260623",
                "tcs_server-1.1.2.1_Patch1_20260624",
            ]
        )
        self.assertEqual(result, "tcs_server-1.1.2.1_Patch1_20260624")

    def test_display_tcs_version_falls_back_to_preferred_version_when_date_missing(self):
        result = monitoring_api._display_tcs_version(
            [
                "tcs_server-1.1.2.1_Patch1",
                "tcs_server-1.1.2.1_Patch2",
            ]
        )
        self.assertEqual(result, "tcs_server-1.1.2.1_Patch2")

    def test_display_tcs_version_prefers_latest_build_date_across_core_and_getway(self):
        result = monitoring_api._display_tcs_version(
            [
                "tcs_server-1.1.2.1_Patch1_20260615",
                "tcs_server-mqm_PC-1020.1.1.2.1_Patch2_mqm_keept_20260623",
            ]
        )
        self.assertEqual(
            result,
            "tcs_server-mqm_PC-1020.1.1.2.1_Patch2_mqm_keept_20260623",
        )


if __name__ == "__main__":
    unittest.main()
