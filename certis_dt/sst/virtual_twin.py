"""
Mirrored Virtual Twin Shadow and State Synchronizer.

Maintains an asynchronous, high-rate virtual representation of the physical UAV,
performing dead-reckoning extrapolation during communication latency and packet drops,
and quantifying synchronization divergence.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from certis_dt.sst.agent import UAVState, AgentRole


@dataclass
class SynchronizationDivergence:
    """Instantaneous difference between physical asset and virtual counterpart."""
    timestamp_s: float
    position_error_m: float
    velocity_error_mps: float
    attitude_error_rad: float
    latency_s: float
    is_synchronized: bool  # True if position_error_m <= threshold (e.g., 0.20 m)


class UAVVirtualTwin:
    """
    Virtual counterpart shadow of a physical UAV asset.
    
    Functions:
      - Ingests delayed/lossy telemetry packets.
      - Extrapolates current state using 2nd-order kinematic dead reckoning:
          p(t) = p_last + v_last * dt + 0.5 * a_last * dt^2
      - Tracks synchronization divergence against ground-truth physical telemetry.
    """

    def __init__(
        self,
        agent_id: str,
        initial_position: Optional[np.ndarray] = None,
        role: AgentRole = AgentRole.WINGMAN_LEFT,
        divergence_threshold_m: float = 0.20,  # 20 cm airworthiness sync bound
    ):
        self.agent_id = agent_id
        self.role = role
        self.divergence_threshold = divergence_threshold_m
        
        # Virtual shadow state
        self.virtual_position = np.array(initial_position if initial_position is not None else [0.0, 0.0, -50.0], dtype=np.float64)
        self.virtual_velocity = np.zeros(3, dtype=np.float64)
        self.virtual_acceleration = np.zeros(3, dtype=np.float64)
        self.virtual_attitude = np.zeros(3, dtype=np.float64)
        
        # Latest received physical telemetry
        self.last_telemetry_time_s = 0.0
        self.last_received_packet_time_s = 0.0
        self.margin_of_safety = 1.0
        self.peak_stress_pa = 0.0
        self.epistemic_credibility = 1.0
        self.refusal_to_certify = False
        self.cumulative_damage = 0.0
        
        # History
        self.divergence_history: List[SynchronizationDivergence] = []
        self.virtual_trajectory: List[Tuple[float, np.ndarray]] = []

    def ingest_telemetry(self, state: UAVState, current_sim_time_s: float) -> None:
        """
        Update shadow state from received telemetry packet with latency compensation.
        
        Extrapolates state forward across communication transmission lag:
          dt_lag = current_sim_time_s - state.timestamp_s
          p_sync = p_rx + v_rx * dt_lag + 0.5 * a_rx * dt_lag^2
        """
        dt_lag = max(0.0, current_sim_time_s - state.timestamp_s)
        
        # Latency-compensated position and velocity
        self.virtual_position = (
            np.copy(state.position)
            + np.copy(state.velocity) * dt_lag
            + 0.5 * np.copy(state.acceleration) * (dt_lag ** 2)
        )
        self.virtual_velocity = np.copy(state.velocity) + np.copy(state.acceleration) * dt_lag
        self.virtual_acceleration = np.copy(state.acceleration)
        self.virtual_attitude = np.copy(state.attitude_rad)
        self.role = state.role
        
        self.last_telemetry_time_s = state.timestamp_s
        self.last_received_packet_time_s = current_sim_time_s
        
        self.margin_of_safety = state.margin_of_safety
        self.peak_stress_pa = state.peak_stress_pa
        self.epistemic_credibility = state.epistemic_credibility
        self.refusal_to_certify = state.refusal_to_certify
        self.cumulative_damage = state.cumulative_damage

    def predict_forward(self, dt: float, current_sim_time_s: float) -> np.ndarray:
        """
        Perform kinematic extrapolation forward during telemetry gap.
        
        p(t + dt) = p(t) + v(t)*dt + 0.5*a(t)*dt^2
        v(t + dt) = v(t) + a(t)*dt
        """
        self.virtual_position += self.virtual_velocity * dt + 0.5 * self.virtual_acceleration * (dt ** 2)
        self.virtual_velocity += self.virtual_acceleration * dt
        
        self.virtual_trajectory.append((current_sim_time_s, np.copy(self.virtual_position)))
        return self.virtual_position

    def compute_divergence(self, truth_state: UAVState, current_sim_time_s: float) -> SynchronizationDivergence:
        """
        Quantify instantaneous discrepancy between physical truth and virtual shadow.
        """
        pos_err = float(np.linalg.norm(truth_state.position - self.virtual_position))
        vel_err = float(np.linalg.norm(truth_state.velocity - self.virtual_velocity))
        att_err = float(np.linalg.norm(truth_state.attitude_rad - self.virtual_attitude))
        latency = current_sim_time_s - self.last_telemetry_time_s
        
        is_synced = bool(pos_err <= self.divergence_threshold)
        
        div = SynchronizationDivergence(
            timestamp_s=current_sim_time_s,
            position_error_m=pos_err,
            velocity_error_mps=vel_err,
            attitude_error_rad=att_err,
            latency_s=latency,
            is_synchronized=is_synced,
        )
        self.divergence_history.append(div)
        return div
