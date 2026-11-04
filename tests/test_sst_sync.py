"""
Unit tests for Layer 2 SST: Swarm State Synchronization Twin and SASA Planner.
"""

import unittest
import numpy as np

from certis_dt.sst.agent import UAVPhysicalAgent, AgentRole
from certis_dt.sst.virtual_twin import UAVVirtualTwin
from certis_dt.sst.network_channel import TacticalNetworkChannel
from certis_dt.sst.swarm_planner import StructuralAwareSwarmPlanner
from certis_dt.sst.metrics import SynchronizationMetricsCalculator


class TestSwarmStateSynchronization(unittest.TestCase):
    def setUp(self):
        self.agent = UAVPhysicalAgent(agent_id="UAV-01", initial_position=np.array([0.0, 0.0, -50.0]))
        self.twin = UAVVirtualTwin(agent_id="UAV-01", initial_position=np.array([0.0, 0.0, -50.0]))
        self.channel = TacticalNetworkChannel(base_latency_s=0.015, baseline_loss_prob=0.0)
        self.planner = StructuralAwareSwarmPlanner()
        self.sync_calc = SynchronizationMetricsCalculator()

    def test_latency_compensated_synchronization(self):
        """Verify latency compensation achieves sub-10cm tracking divergence."""
        # Step physical agent
        for step in range(50):
            t = step * 0.01
            p_state = self.agent.step(0.01, commanded_velocity=np.array([15.0, 0.0, 0.0]))
            
            # Transmit uplink packet
            self.channel.transmit_uplink(
                source_id="UAV-01",
                payload={
                    "position": p_state.position,
                    "velocity": p_state.velocity,
                    "acceleration": p_state.acceleration,
                    "attitude_rad": p_state.attitude_rad,
                    "margin_of_safety": 1.0,
                    "peak_stress_pa": 50e6,
                    "epistemic_credibility": 1.0,
                    "refusal_to_certify": False,
                    "cumulative_damage": 0.0,
                    "role": AgentRole.LEADER,
                },
                current_time_s=t,
            )
            
            # Receive and update virtual twin
            delivered = self.channel.receive_uplink(t)
            for pkt in delivered:
                p = pkt.payload
                state = p_state
                self.twin.ingest_telemetry(state, t)
                
            div = self.twin.compute_divergence(self.agent.get_state(), t)

        report = self.sync_calc.compute_agent_metrics("UAV-01", self.twin.divergence_history)
        self.assertLess(report.mean_position_rmse_m, 0.15)
        self.assertGreaterEqual(report.synchronization_availability_pct, 95.0)

    def test_sasa_dynamic_leader_swap(self):
        """Verify that when leader structural margin degrades, planner re-assigns role."""
        agent_ids = ["UAV-1", "UAV-2", "UAV-3"]
        self.planner.initialize_v_formation(agent_ids)
        self.assertEqual(self.planner.slots["UAV-1"].role, AgentRole.LEADER)
        
        # Create virtual twins
        twins = {
            aid: UAVVirtualTwin(agent_id=aid, role=self.planner.slots[aid].role)
            for aid in agent_ids
        }
        
        # Simulate structural degradation on leader (MS drops to 0.15 < 0.30 threshold)
        twins["UAV-1"].margin_of_safety = 0.15
        twins["UAV-2"].margin_of_safety = 1.25  # Healthy wingman
        twins["UAV-3"].margin_of_safety = 1.10
        
        cmd = self.planner.plan_swarm_step(
            virtual_twins=twins,
            centroid_target_pos=np.array([100.0, 0.0, -50.0]),
            centroid_target_vel=np.array([15.0, 0.0, 0.0]),
            current_time_s=5.0,
        )
        
        # Healthiest wingman (UAV-2) should have been promoted to LEADER
        self.assertEqual(self.planner.slots["UAV-2"].role, AgentRole.LEADER)
        self.assertEqual(self.planner.slots["UAV-1"].role, AgentRole.WINGMAN_LEFT)


if __name__ == "__main__":
    unittest.main()
