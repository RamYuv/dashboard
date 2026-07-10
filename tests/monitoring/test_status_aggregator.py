import unittest

from monitoring.services.status_aggregator import EnvStatusAggregator


class EnvStatusAggregatorTests(unittest.TestCase):
    def setUp(self):
        self.aggregator = EnvStatusAggregator()

    def test_environment_is_red_when_one_vm_is_green_and_another_is_yellow(self):
        result = self.aggregator._calculate_env_color(["Green", "Yellow"])
        self.assertEqual(result, "Red")

    def test_environment_stays_yellow_when_all_vms_are_yellow(self):
        result = self.aggregator._calculate_env_color(["Yellow", "Yellow"])
        self.assertEqual(result, "Yellow")

    def test_environment_stays_green_when_all_vms_are_green(self):
        result = self.aggregator._calculate_env_color(["Green", "Green"])
        self.assertEqual(result, "Green")

    def test_environment_is_red_when_one_vm_is_red_and_another_is_yellow(self):
        result = self.aggregator._calculate_env_color(["Red", "Yellow"])
        self.assertEqual(result, "Red")

    def test_environment_is_red_when_all_vms_are_red(self):
        result = self.aggregator._calculate_env_color(["Red", "Red"])
        self.assertEqual(result, "Red")

    def test_aggregate_env_statuses_keeps_each_environment_isolated(self):
        vm_statuses = {
            "DEV01:Core": {"vm_color": "Red", "component_data": {}},
            "DEV01:Getway": {"vm_color": "Yellow", "component_data": {}},
            "DEV02:Core": {"vm_color": "Green", "component_data": {}},
            "DEV02:Getway": {"vm_color": "Green", "component_data": {}},
        }
        environments = [
            {"env_id": "DEV01", "env_type": "DEV", "vms": ["DEV01:Core", "DEV01:Getway"]},
            {"env_id": "DEV02", "env_type": "DEV", "vms": ["DEV02:Core", "DEV02:Getway"]},
        ]

        result = self.aggregator.aggregate_env_statuses(vm_statuses, environments)

        self.assertEqual(result["DEV01"]["env_color"], "Red")
        self.assertEqual(result["DEV02"]["env_color"], "Green")
        self.assertEqual(set(result["DEV01"]["vm_details"].keys()), {"DEV01:Core", "DEV01:Getway"})
        self.assertEqual(set(result["DEV02"]["vm_details"].keys()), {"DEV02:Core", "DEV02:Getway"})


if __name__ == "__main__":
    unittest.main()
