"""
Physical UAV Agent Kinematics and Health State Vector.

Implements 6-DOF trajectory kinematics, battery dynamics, and structural health
coupling for individual agents within a supervised autonomous swarm.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np


class AgentRole(Enum):
    LEADER = "LEADER"
    WINGMAN_LEFT = "WINGMAN_LEFT"
    WINGMAN_RIGHT = "WINGMAN_RIGHT"
    SCOUT = "SCOUT"
    FALLBACK_RTB = "FALLBACK_RTB"


@dataclass
class UAVState:
    """Complete physical state vector of a single UAV agent."""
    agent_id: str
    timestamp_s: float
    # 6-DOF Kinematics
    position: np.ndarray        # [x, y, z] in meters (NED or ENU frame)
    velocity: np.ndarray        # [vx, vy, vz] in m/s
    attitude_rad: np.ndarray    # [roll, pitch, yaw] in radians
    angular_velocity: np.ndarray # [p, q, r] in rad/s
    acceleration: np.ndarray    # [ax, ay, az] in m/s^2
    # Structural & Health States (Coupled from SCT)
    margin_of_safety: float     # Critical structural MS
    peak_stress_pa: float       # Current peak stress in Pa
    epistemic_credibility: float # Epistemic credibility in [0, 1]
    refusal_to_certify: bool    # True if surrogate refused certification
    cumulative_damage: float    # Fatigue damage D in [0, 1]
    # Mission & System States
    battery_charge_pct: float   # 0 to 100%
    role: AgentRole = AgentRole.WINGMAN_LEFT


class UAVPhysicalAgent:
    """
    Physical UAV asset executing flight trajectory with coupled structural telemetry.
    """

    def __init__(
        self,
        agent_id: str,
        initial_position: Optional[np.ndarray] = None,
        role: AgentRole = AgentRole.WINGMAN_LEFT,
        mass_kg: float = 4.5,
        max_thrust_n: float = 90.0,
        max_speed_mps: float = 22.0,
    ):
        self.agent_id = agent_id
        self.role = role
        self.mass = mass_kg
        self.max_thrust = max_thrust_n
        self.max_speed = max_speed_mps
        
        # State vectors
        self.position = np.array(initial_position if initial_position is not None else [0.0, 0.0, -50.0], dtype=np.float64)
        self.velocity = np.zeros(3, dtype=np.float64)
        self.attitude = np.zeros(3, dtype=np.float64)
        self.angular_velocity = np.zeros(3, dtype=np.float64)
        self.acceleration = np.zeros(3, dtype=np.float64)
        self.battery_pct = 100.0
        self.time = 0.0
        
        # Coupled structural state
        self.margin_of_safety = 1.20
        self.peak_stress_pa = 50.0e6
        self.epistemic_credibility = 1.0
        self.refusal_to_certify = False
        self.cumulative_damage = 0.0

    def update_structural_state(
        self,
        margin_of_safety: float,
        peak_stress_pa: float,
        epistemic_credibility: float,
        refusal_to_certify: bool,
        cumulative_damage: float,
    ) -> None:
        """Inject latest assessment from Layer 1 SCT."""
        self.margin_of_safety = margin_of_safety
        self.peak_stress_pa = peak_stress_pa
        self.epistemic_credibility = epistemic_credibility
        self.refusal_to_certify = refusal_to_certify
        self.cumulative_damage = cumulative_damage

    def step(
        self,
        dt: float,
        commanded_velocity: np.ndarray,
        wind_gust: Optional[np.ndarray] = None,
    ) -> UAVState:
        """
        Advance physical agent kinematics by dt seconds under velocity controller.
        
        Args:
            dt: Timestep in seconds.
            commanded_velocity: Target [vx, vy, vz] in m/s.
            wind_gust: Aerodynamic wind disturbance vector [wx, wy, wz] in m/s.
        """
        # Aerodynamic and control limits
        cmd_v = np.clip(commanded_velocity, -self.max_speed, self.max_speed)
        gust = wind_gust if wind_gust is not None else np.zeros(3)
        
        # 1st-order velocity autopilot tracking: a = (v_cmd - v) / tau_accel
        tau_accel = 0.35  # seconds
        target_accel = (cmd_v - self.velocity) / tau_accel
        
        # Clamp acceleration within UAV thrust envelope (e.g., max 3.5g)
        max_accel = 34.3  # 3.5 g
        accel_norm = np.linalg.norm(target_accel)
        if accel_norm > max_accel:
            target_accel = target_accel * (max_accel / accel_norm)
            
        self.acceleration = target_accel + 0.15 * gust
        self.velocity += self.acceleration * dt
        self.position += (self.velocity + gust) * dt
        self.time += dt
        
        # Simple attitude approximation from velocity/acceleration
        speed = np.linalg.norm(self.velocity[:2])
        if speed > 0.5:
            self.attitude[2] = np.arctan2(self.velocity[1], self.velocity[0])  # Yaw
        self.attitude[1] = np.clip(-self.acceleration[0] / 9.81, -0.6, 0.6)    # Pitch
        self.attitude[0] = np.clip(self.acceleration[1] / 9.81, -0.6, 0.6)     # Roll
        
        # Battery drain: baseline + thrust power
        power_drain = 0.005 + 0.001 * (np.linalg.norm(self.velocity) ** 1.5)
        self.battery_pct = max(0.0, self.battery_pct - power_drain * dt)
        
        return self.get_state()

    def get_state(self) -> UAVState:
        """Snapshot current state."""
        return UAVState(
            agent_id=self.agent_id,
            timestamp_s=self.time,
            position=np.copy(self.position),
            velocity=np.copy(self.velocity),
            attitude_rad=np.copy(self.attitude),
            angular_velocity=np.copy(self.angular_velocity),
            acceleration=np.copy(self.acceleration),
            margin_of_safety=self.margin_of_safety,
            peak_stress_pa=self.peak_stress_pa,
            epistemic_credibility=self.epistemic_credibility,
            refusal_to_certify=self.refusal_to_certify,
            cumulative_damage=self.cumulative_damage,
            battery_charge_pct=self.battery_pct,
            role=self.role,
        )
