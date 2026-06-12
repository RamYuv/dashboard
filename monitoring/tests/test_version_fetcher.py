import unittest

from monitoring.services.version_fetcher import VersionFetcher


class SimpleExecutor:
    def __init__(self, output, ok=True, exit_code=0, stderr=""):
        self.output = output
        self.ok = ok
        self.exit_code = exit_code
        self.stderr = stderr

    def run(self, host, username, password, command):
        class Result:
            def __init__(self, stdout, stderr, exit_code, ok):
                self.stdout = stdout
                self.stderr = stderr
                self.exit_code = exit_code
                self.ok = ok

            @property
            def combined_output(self):
                return "\n".join(part for part in [self.stdout or "", self.stderr or ""] if part)

        return Result(self.output, self.stderr, self.exit_code, self.ok)


class VersionFetcherTests(unittest.TestCase):
    def test_parse_output_json_mapping(self):
        fetcher = VersionFetcher(executor=SimpleExecutor('{}'))
        parsed = fetcher.parse_output('{"core": "1.2.3", "gateway": "4.5.6"}')
        self.assertEqual(parsed["versions"], {"core": "1.2.3", "gateway": "4.5.6"})
        self.assertEqual(parsed["deployment_details"], {"mode": "", "service_types": []})
        self.assertEqual(parsed["raw_output"], '{"core": "1.2.3", "gateway": "4.5.6"}')

    def test_parse_output_plain_lines(self):
        fetcher = VersionFetcher(executor=SimpleExecutor('core: 1.2.3\ngateway: 4.5.6'))
        parsed = fetcher.parse_output('core: 1.2.3\ngateway: 4.5.6')
        self.assertEqual(parsed["versions"], {"core": "1.2.3", "gateway": "4.5.6"})
        self.assertEqual(parsed["deployment_details"], {"mode": "", "service_types": []})
        self.assertEqual(parsed["raw_output"], 'core: 1.2.3\ngateway: 4.5.6')

    def test_parse_output_empty_string(self):
        fetcher = VersionFetcher(executor=SimpleExecutor(''))
        parsed = fetcher.parse_output('')
        self.assertEqual(parsed["versions"], {})
        self.assertEqual(parsed["deployment_details"], {"mode": "", "service_types": []})
        self.assertEqual(parsed["raw_output"], "")

    def test_parse_output_invalid_json_falls_back_to_lines(self):
        fetcher = VersionFetcher(executor=SimpleExecutor('core: 1.2.3\nnotjson'))
        parsed = fetcher.parse_output('core: 1.2.3\nnotjson')
        self.assertEqual(parsed["versions"], {"core": "1.2.3"})
        self.assertEqual(parsed["deployment_details"], {"mode": "", "service_types": []})
        self.assertEqual(parsed["raw_output"], 'core: 1.2.3\nnotjson')

    def test_parse_output_extracts_deployment_details_from_deploy_info(self):
        fetcher = VersionFetcher(executor=SimpleExecutor(''))
        parsed = fetcher.parse_output(
            """
[Deploy Info]
env_name = DEV01
server = gateway
install_user = pali
deploy_service = DOM CONV
mode = RT
versions = tcs_service-1.1.2.3_20260604
""".strip()
        )
        self.assertEqual(parsed["versions"], {"gateway": "tcs_service-1.1.2.3_20260604"})
        self.assertEqual(parsed["deployment_details"], {"mode": "RT", "service_types": ["DOM", "CONV"]})

    def test_fetch_versions_returns_mapping_and_raw_output(self):
        executor = SimpleExecutor('core: 1.2.3')
        fetcher = VersionFetcher(executor=executor)
        mapping, raw = fetcher.fetch_versions('host', 'user', 'pass', server_type='core')
        self.assertEqual(mapping, {"core": "1.2.3"})
        self.assertEqual(raw, 'core: 1.2.3')


if __name__ == '__main__':
    unittest.main()
