"""
Unit tests for HIL Fault Injection Engine and TRL 5 Harness.
"""

import unittest
import numpy as np

from certis_dt.hil.fault_injector import FaultInjector, FaultProfile, FaultMode
from certis_dt.hil.trl5_evaluator import TRL5MissionHarness


class TestFaultInjection(unittest.TestCase):
    def test_sensor_fault_application(self):
        """Verify sensor fault injector properly corrupts telemetry."""
        injector = FaultInjector([
            FaultProfile(
                fault_mode=FaultMode.SENSOR_DISCONNECT_DROP,
                start_time_s=1.0,
                end_time_s=3.0,
                target_agent_id="UAV-01",
                target_sensor_id="SG-02",
            )
        ])
        
        station_ids = ["SG-01", "SG-02", "SG-03"]
        raw = np.array([50e-6, 40e-6, 30e-6])
        
        # Before fault window
        c_before = injector.apply_sensor_faults("UAV-01", 0.5, station_ids, raw)
        self.assertEqual(c_before[1], 40e-6)
        
        # Inside fault window
        c_during = injector.apply_sensor_faults("UAV-01", 1.5, station_ids, raw)
        self.assertEqual(c_during[1], 0.0)  # SG-02 disconnected
        self.assertEqual(c_during[0], 50e-6)  # Other sensors untouched

    def test_trl5_mission_harness_execution(self):
        """Verify end-to-end mission harness completes simulation without error."""
        harness = TRL5MissionHarness(agent_ids=["UAV-1", "UAV-2"], dt_seconds=0.01)
        res = harness.run_mission(duration_s=1.5)
        self.assertEqual(res.total_steps, 150)
        self.assertIn("UAV-1", res.structural_margins)
        self.assertIn("UAV-1", res.sync_reports)


if __name__ == "__main__":
    unittest.main()
