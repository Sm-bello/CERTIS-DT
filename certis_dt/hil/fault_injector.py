"""
Hardware-In-The-Loop (HIL) Fault Injection Engine.

Simulates physical and cyber-physical failure modes including strain gauge debonding,
wiring disconnection, RF jamming, and severe atmospheric gust microbursts.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np


class FaultMode(Enum):
    NONE = "NONE"
    SENSOR_BIAS_DRIFT = "SENSOR_BIAS_DRIFT"              # Linear sensor drift (strain gauge creep/debonding)
    SENSOR_DISCONNECT_DROP = "SENSOR_DISCONNECT_DROP"    # Sudden signal loss / flatline
    COMMS_JAMMING_BURST = "COMMS_JAMMING_BURST"          # RF electronic warfare / high packet loss
    EXTREME_MICROBURST_GUST = "EXTREME_MICROBURST_GUST"  # Non-stationary aerodynamic shock load


@dataclass
class FaultProfile:
    fault_mode: FaultMode
    start_time_s: float
    end_time_s: float
    target_agent_id: str
    target_sensor_id: Optional[str] = None
    magnitude: float = 1.0  # Normalized scale or physical severity


class FaultInjector:
    """
    Orchestrates fault injection across physical structural dynamics and communication channels.
    """

    def __init__(self, profiles: Optional[List[FaultProfile]] = None):
        self.profiles = profiles or []

    def add_fault(self, profile: FaultProfile) -> None:
        self.profiles.append(profile)

    def apply_sensor_faults(
        self,
        agent_id: str,
        current_time_s: float,
        station_ids: List[str],
        measured_strains: np.ndarray,
    ) -> np.ndarray:
        """Modify sensor readings if an active sensor fault profile applies."""
        corrupted = np.copy(measured_strains)
        
        for p in self.profiles:
            if p.target_agent_id != agent_id:
                continue
            if not (p.start_time_s <= current_time_s <= p.end_time_s):
                continue
                
            if p.fault_mode == FaultMode.SENSOR_DISCONNECT_DROP:
                for idx, sid in enumerate(station_ids):
                    if p.target_sensor_id is None or sid == p.target_sensor_id:
                        corrupted[idx] = 0.0  # Disconnected line reads zero
            elif p.fault_mode == FaultMode.SENSOR_BIAS_DRIFT:
                elapsed = current_time_s - p.start_time_s
                drift = p.magnitude * 1e-6 * elapsed  # microstrain per second
                for idx, sid in enumerate(station_ids):
                    if p.target_sensor_id is None or sid == p.target_sensor_id:
                        corrupted[idx] += drift
                        
        return corrupted

    def get_aerodynamic_disturbance(
        self,
        agent_id: str,
        current_time_s: float,
        nominal_gust: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """
        Compute total gust vector and tip load force spike.
        
        Returns:
            Tuple: (wind_velocity_vector [3,], tip_force_spike_n)
        """
        gust = np.copy(nominal_gust)
        force_spike = 0.0
        
        for p in self.profiles:
            if p.target_agent_id != agent_id:
                continue
            if not (p.start_time_s <= current_time_s <= p.end_time_s):
                continue
                
            if p.fault_mode == FaultMode.EXTREME_MICROBURST_GUST:
                # Severe vertical microburst downdraft
                tau = (current_time_s - p.start_time_s) / max(0.1, p.end_time_s - p.start_time_s)
                # Half-sine pulse load
                pulse = np.sin(np.pi * np.clip(tau, 0.0, 1.0))
                gust[2] += p.magnitude * 12.0 * pulse  # Downward gust in m/s
                force_spike += p.magnitude * 180.0 * pulse  # Dynamic load spike in N
                
        return gust, force_spike
