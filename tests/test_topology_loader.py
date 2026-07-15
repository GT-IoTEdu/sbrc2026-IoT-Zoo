#!/usr/bin/env python3
"""Smoke tests for the IoT-Zoo configuration-driven topology loader."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import topology_loader as loader  # noqa: E402


class TopologyLoaderSmokeTest(unittest.TestCase):
    def test_default_topology_expands_to_original_size(self):
        plan = loader.load(os.path.join(PROJECT_ROOT, "topology.yaml"))
        self.assertEqual(len(plan["switches"]), 1)
        self.assertEqual(len(plan["services"]), 2)
        self.assertEqual(len(plan["profiles"]), 43)
        self.assertEqual(len(plan["services"]) + len(plan["profiles"]) + 1, 46)

    def test_tree_example_expands(self):
        plan = loader.load(os.path.join(PROJECT_ROOT, "topology_example_tree.yaml"))
        self.assertEqual(plan["switches"], ["s1", "s2", "s3"])
        self.assertEqual(len(plan["services"]), 3)
        self.assertEqual(len(plan["profiles"]), 11)
        self.assertEqual(len(plan["links"]), 2)

    def test_broker_scaling(self):
        plan = loader.load(os.path.join(PROJECT_ROOT, "topology.yaml"), brokers=2)
        broker_names = [s["name"] for s in plan["services"] if s.get("kind") == "mqtt_broker"]
        self.assertEqual(broker_names, ["broker_1", "broker_2"])

    def test_device_replication_without_diversity_is_rejected(self):
        with self.assertRaises(loader.TopologyError):
            loader.load(os.path.join(PROJECT_ROOT, "topology.yaml"), scale={"predio": 2})


if __name__ == "__main__":
    unittest.main()
