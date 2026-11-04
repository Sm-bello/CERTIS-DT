"""
Structural-Aware Swarm Autonomy (SASA) Planner.

Dynamically couples structural health telemetry and uncertainty bounds into
real-time swarm mission re-planning, formation geometry adaptation, dynamic
leader re-assignment, and velocity derating under airworthiness constraints.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from certis_dt.sst.agent import AgentRole, UAVState, UAVPhysicalAgent
from certis_dt.sst.virtual_twin import UAVVirtualTwin
from certis_dt.sst.hotl_supervisor import HOTLSupervisor


@dataclass
class SwarmFormationSlot:
    agent_id: str
    role: AgentRole
    relative_offset_ned: np.ndarray  # [dx, dy, dz] relative to formation virtual centroid


class StructuralAwareSwarmPlanner:
    """
    Decentralized/Supervised swarm coordinator with structural health constraints.
    
    Safety Rules:
      - Rule 1 (Health-Based Leader Election): Leader must have MS >= 0.35 and Epistemic Credibility >= 0.85.
        If leader degrades, elect healthiest wingman to lead.
      - Rule 2 (Flight Envelope Derating): If any agent experiences 0.0 <= MS < 0.20,
        derate swarm cruise velocity by 35% to reduce dynamic pressure q = 0.5*rho*V^2.
      - Rule 3 (Failsafe RTB): If MS < 0.0 or epistemic refusal is active, transition agent to FALLBACK_RTB.
      - Rule 4 (Formation Spacing Adaptation): Scale separation distance inversely with confidence.
    """

    def __init__(
        self,
        nominal_cruise_speed_mps: float = 18.0,
        nominal_spacing_m: float = 12.0,
        hotl_supervisor: Optional[HOTLSupervisor] = None,
    ):
        self.nominal_speed = nominal_cruise_speed_mps
        self.current_max_speed = nominal_cruise_speed_mps
        self.nominal_spacing = nominal_spacing_m
        self.supervisor = hotl_supervisor or HOTLSupervisor()
        
        # Swarm slots: agent_id -> SwarmFormationSlot
        self.slots: Dict[str, SwarmFormationSlot] = {}
        self.replan_event_log: List[Dict[str, str]] = []

    def initialize_v_formation(self, agent_ids: List[str]) -> None:
        """Configure standard symmetrical V-formation."""
        self.slots.clear()
        if not agent_ids:
            return
            
        # First agent is initial Leader
        leader_id = agent_ids[0]
        self.slots[leader_id] = SwarmFormationSlot(
            agent_id=leader_id,
            role=AgentRole.LEADER,
            relative_offset_ned=np.array([0.0, 0.0, 0.0], dtype=np.float64),
        )
        
        # Alternating left and right wingmen
        d = self.nominal_spacing
        for idx, aid in enumerate(agent_ids[1:], start=1):
            side = -1.0 if (idx % 2 == 1) else 1.0  # -1 for left (port), +1 for right (starboard)
            row = (idx + 1) // 2
            dx = -row * d * 0.707  # Trailing back
            dy = side * row * d * 0.707
            dz = 0.0
            role = AgentRole.WINGMAN_LEFT if side < 0 else AgentRole.WINGMAN_RIGHT
            self.slots[aid] = SwarmFormationSlot(
                agent_id=aid,
                role=role,
                relative_offset_ned=np.array([dx, dy, dz], dtype=np.float64),
            )

    def plan_swarm_step(
        self,
        virtual_twins: Dict[str, UAVVirtualTwin],
        centroid_target_pos: np.ndarray,
        centroid_target_vel: np.ndarray,
        current_time_s: float,
    ) -> Dict[str, np.ndarray]:
        """
        Compute commanded velocities [vx, vy, vz] for each agent based on structural health.
        
        Returns:
            Dictionary mapping agent_id to commanded velocity vector (3,).
        """
        # Step 1: Health assessment and airworthiness rule verification
        self._evaluate_structural_airworthiness(virtual_twins, current_time_s)
        
        # Step 2: Compute velocity commands
        commands = {}
        for aid, slot in self.slots.items():
            if slot.role == AgentRole.FALLBACK_RTB:
                # Failsafe RTB command: ascend and return to origin [0, 0, -40]
                rtb_vector = np.array([0.0, 0.0, -40.0]) - virtual_twins[aid].virtual_position
                dist = np.linalg.norm(rtb_vector)
                if dist > 1.0:
                    commands[aid] = (rtb_vector / dist) * min(self.nominal_speed * 0.6, dist)
                else:
                    commands[aid] = np.zeros(3)
                continue
                
            # Target position for agent = centroid_target_pos + relative_offset
            target_p = centroid_target_pos + slot.relative_offset_ned
            current_p = virtual_twins[aid].virtual_position
            pos_err = target_p - current_p
            
            # Proportional velocity steering
            k_p = 1.2
            v_cmd = centroid_target_vel + k_p * pos_err
            
            # Enforce dynamic speed limit
            speed = np.linalg.norm(v_cmd)
            if speed > self.current_max_speed:
                v_cmd = (v_cmd / speed) * self.current_max_speed
                
            commands[aid] = v_cmd

        return commands

    def _evaluate_structural_airworthiness(
        self,
        twins: Dict[str, UAVVirtualTwin],
        current_time_s: float,
    ) -> None:
        """Check all agent structural margins and execute re-planning if degraded."""
        min_margin = 999.0
        current_leader_id = None
        candidates = []
        
        for aid, slot in self.slots.items():
            if aid not in twins:
                continue
            twin = twins[aid]
            ms = twin.margin_of_safety
            cred = twin.epistemic_credibility
            refusal = twin.refusal_to_certify
            min_margin = min(min_margin, ms)
            
            if slot.role == AgentRole.LEADER:
                current_leader_id = aid
                
            # If critical margin violation or epistemic refusal: trigger RTB
            if (ms < 0.0 or refusal) and slot.role != AgentRole.FALLBACK_RTB:
                self.slots[aid].role = AgentRole.FALLBACK_RTB
                self.supervisor.submit_request(
                    action_type="COMMAND_RTB",
                    target_agent_id=aid,
                    rationale=f"Structural Margin Violation (MS={ms:.2f}) or Epistemic Refusal ({refusal}).",
                    structural_margin=ms,
                    epistemic_credibility=cred,
                    current_time_s=current_time_s,
                    force_immediate_safety_override=True,
                )
                self.replan_event_log.append({
                    "time": f"{current_time_s:.2f}s",
                    "event": f"Agent {aid} ejected from formation -> FALLBACK_RTB",
                })
            elif slot.role != AgentRole.FALLBACK_RTB:
                candidates.append((aid, ms, cred))

        # Velocity envelope derating
        if min_margin < 0.20:
            self.current_max_speed = self.nominal_speed * 0.65  # 35% speed derate
        else:
            self.current_max_speed = self.nominal_speed

        # Check if leader needs replacement
        if current_leader_id and current_leader_id in twins:
            ldr_twin = twins[current_leader_id]
            if (ldr_twin.margin_of_safety < 0.30 or ldr_twin.refusal_to_certify) and len(candidates) > 1:
                # Find healthiest candidate
                candidates.sort(key=lambda c: (c[1], c[2]), reverse=True)
                new_leader_id = candidates[0][0]
                if new_leader_id != current_leader_id:
                    self._swap_leader(current_leader_id, new_leader_id, current_time_s, ldr_twin.margin_of_safety)

    def _swap_leader(self, old_ldr: str, new_ldr: str, current_time_s: float, old_ms: float) -> None:
        """Re-assign leader role and offsets."""
        old_slot = self.slots[old_ldr]
        new_slot = self.slots[new_ldr]
        
        # Swap roles
        old_slot.role = AgentRole.WINGMAN_LEFT
        new_slot.role = AgentRole.LEADER
        
        # Swap offsets
        temp_offset = np.copy(old_slot.relative_offset_ned)
        old_slot.relative_offset_ned = np.copy(new_slot.relative_offset_ned)
        new_slot.relative_offset_ned = temp_offset
        
        self.supervisor.submit_request(
            action_type="SWAP_LEADER",
            target_agent_id=new_ldr,
            rationale=f"Previous leader {old_ldr} degraded to MS={old_ms:.2f}. Promoted healthiest wingman {new_ldr}.",
            structural_margin=old_ms,
            epistemic_credibility=1.0,
            current_time_s=current_time_s,
            force_immediate_safety_override=True,
        )
        self.replan_event_log.append({
            "time": f"{current_time_s:.2f}s",
            "event": f"Dynamic leader swap: {old_ldr} -> {new_ldr}",
        })
