#!/usr/bin/env python3
"""Smoke tests for the L3-segmented institutional IoT-Zoo topology."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import topology_loader as loader  # noqa: E402


class L3SegmentedTopologyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = loader.load(os.path.join(PROJECT_ROOT, "topology_l3_segmented_institutional.yaml"))

    def test_l3_mode_and_core_shape(self):
        self.assertEqual(self.plan["mode"], "l3")
        self.assertEqual(len(self.plan["routers"]), 2)
        self.assertEqual({r["name"] for r in self.plan["routers"]}, {"r_edge", "r_field"})
        self.assertEqual(len(self.plan["switches"]), 8)
        self.assertEqual(len(self.plan["networks"]), 8)

    def test_exact_subnets_and_gateways(self):
        expected = {
            "external": ("10.10.0.0/24", "10.10.0.1"),
            "infra": ("10.20.0.0/24", "10.20.0.1"),
            "hospital": ("10.30.1.0/24", "10.30.1.1"),
            "university": ("10.30.2.0/24", "10.30.2.1"),
            "industrial": ("10.30.3.0/24", "10.30.3.1"),
            "school": ("10.30.4.0/24", "10.30.4.1"),
            "cctv": ("10.30.5.0/24", "10.30.5.1"),
            "outdoor": ("10.30.6.0/24", "10.30.6.1"),
        }
        for name, (subnet, gateway) in expected.items():
            self.assertEqual(self.plan["networks"][name]["subnet"], subnet)
            self.assertEqual(self.plan["networks"][name]["gateway"], gateway)

    def test_router_interfaces_match_figure(self):
        routers = {r["name"]: r for r in self.plan["routers"]}
        r_edge = {i["network"]: i["ip"] for i in routers["r_edge"]["interfaces"]}
        self.assertEqual(r_edge, {"external": "10.10.0.1", "infra": "10.20.0.1"})
        r_field = {i["network"]: i["ip"] for i in routers["r_field"]["interfaces"]}
        self.assertEqual(r_field["infra"], "10.20.0.254")
        self.assertEqual(r_field["hospital"], "10.30.1.1")
        self.assertEqual(r_field["outdoor"], "10.30.6.1")

    def test_representative_services_and_profiles(self):
        services = {s["name"]: s for s in self.plan["services"]}
        self.assertEqual(services["broker_core"]["ip"], "10.20.0.100")
        self.assertEqual(services["rtsp_server"]["ip"], "10.20.0.20")
        self.assertEqual(services["benign_dashboard"]["ip"], "10.10.0.30")
        profiles = {p["name"]: p for p in self.plan["profiles"]}
        self.assertEqual(profiles["mhealth_device_1"]["ip"], "10.30.1.11")
        self.assertEqual(profiles["ip_camera_2"]["env"]["STREAM_SERVER_ADDR"], "10.20.0.20")
        self.assertEqual(profiles["gw_co"]["env"]["MQTT_BROKER_ADDR"], "10.30.6.100")

    def test_capture_includes_all_domain_switches_and_router_interfaces(self):
        points = set(self.plan["capture"]["points"])
        for point in [
            "sw_hospital", "sw_university", "sw_industrial", "sw_school", "sw_cctv", "sw_outdoor",
            "r_edge:external", "r_edge:infra", "r_field:infra", "r_field:outdoor",
        ]:
            self.assertIn(point, points)


if __name__ == "__main__":
    unittest.main()
