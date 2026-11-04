"""
Swarm State Synchronization Twin (SST) Module.

Provides physical UAV kinematics, tactical lossy communication modeling,
mirrored virtual twin shadow synchronization, Human-On-The-Loop (HOTL)
supervisory decision gating, and Structural-Aware Swarm Autonomy (SASA) re-planning.
"""

from certis_dt.sst.agent import UAVPhysicalAgent, UAVState, AgentRole
from certis_dt.sst.network_channel import TacticalNetworkChannel, TelemetryPacket
from certis_dt.sst.virtual_twin import UAVVirtualTwin, SynchronizationDivergence
from certis_dt.sst.hotl_supervisor import HOTLSupervisor, SupervisoryActionRequest, AutonomyLevel
from certis_dt.sst.swarm_planner import StructuralAwareSwarmPlanner, SwarmFormationSlot
from certis_dt.sst.metrics import SynchronizationMetricsCalculator, SwarmSynchronizationReport

__all__ = [
    "UAVPhysicalAgent",
    "UAVState",
    "AgentRole",
    "TacticalNetworkChannel",
    "TelemetryPacket",
    "UAVVirtualTwin",
    "SynchronizationDivergence",
    "HOTLSupervisor",
    "SupervisoryActionRequest",
    "AutonomyLevel",
    "StructuralAwareSwarmPlanner",
    "SwarmFormationSlot",
    "SynchronizationMetricsCalculator",
    "SwarmSynchronizationReport",
]
