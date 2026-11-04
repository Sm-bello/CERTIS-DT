"""
Human-On-The-Loop (HOTL) Supervisory Control and Decision Gating.

Implements EASA AI Roadmap 2.0 Level 2 Human-AI Teaming governance, managing
decision authority, supervisory concurrence windows, and fail-safe transitions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time


class AutonomyLevel(Enum):
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"          # Human has direct manual override authority
    HOTL_CONCURRENCE = "HOTL_CONCURRENCE"        # Twin proposes actions; human confirms or times out
    AUTONOMOUS_SAFEGUARD = "AUTONOMOUS_SAFEGUARD" # Real-time structural safety overrides auto-execute


@dataclass
class SupervisoryActionRequest:
    request_id: str
    timestamp_s: float
    action_type: str            # e.g., "SWAP_LEADER", "DERATE_ENVELOPE", "COMMAND_RTB"
    target_agent_id: str
    rationale: str
    structural_margin: float
    epistemic_credibility: float
    timeout_s: float = 2.0
    is_executed: bool = False
    is_rejected: bool = False
    is_auto_committed: bool = False


class HOTLSupervisor:
    """
    Supervises human-AI decision distribution under airworthiness guidelines.
    
    Ensures that safety-critical structural mitigations occur instantaneously while
    tactical mission changes preserve explainable human oversight.
    """

    def __init__(
        self,
        default_autonomy_level: AutonomyLevel = AutonomyLevel.HOTL_CONCURRENCE,
        auto_commit_timeout_s: float = 2.0,
    ):
        self.autonomy_level = default_autonomy_level
        self.timeout_s = auto_commit_timeout_s
        self.pending_requests: List[SupervisoryActionRequest] = []
        self.action_history: List[SupervisoryActionRequest] = []
        self._request_counter = 0

    def submit_request(
        self,
        action_type: str,
        target_agent_id: str,
        rationale: str,
        structural_margin: float,
        epistemic_credibility: float,
        current_time_s: float,
        force_immediate_safety_override: bool = False,
    ) -> SupervisoryActionRequest:
        """
        Submit a proposed reconfiguration action for supervisory evaluation.
        """
        self._request_counter += 1
        req_id = f"HOTL-REQ-{self._request_counter:04d}"
        
        req = SupervisoryActionRequest(
            request_id=req_id,
            timestamp_s=current_time_s,
            action_type=action_type,
            target_agent_id=target_agent_id,
            rationale=rationale,
            structural_margin=structural_margin,
            epistemic_credibility=epistemic_credibility,
            timeout_s=self.timeout_s,
        )
        
        # If emergency safety safeguard or pre-authorized
        if force_immediate_safety_override or self.autonomy_level == AutonomyLevel.AUTONOMOUS_SAFEGUARD:
            req.is_executed = True
            req.is_auto_committed = True
            self.action_history.append(req)
        else:
            self.pending_requests.append(req)
            
        return req

    def process_pending_requests(self, current_time_s: float) -> List[SupervisoryActionRequest]:
        """
        Evaluate timeouts for pending requests (auto-commit if timeout exceeded under HOTL).
        """
        committed = []
        remaining = []
        for req in self.pending_requests:
            elapsed = current_time_s - req.timestamp_s
            if elapsed >= req.timeout_s:
                # Auto-commit under safety-oriented HOTL protocol
                req.is_executed = True
                req.is_auto_committed = True
                committed.append(req)
                self.action_history.append(req)
            else:
                remaining.append(req)
        self.pending_requests = remaining
        return committed

    def human_intervene(self, request_id: str, approve: bool) -> Optional[SupervisoryActionRequest]:
        """Human operator explicitly approves or vetoes a pending request."""
        for idx, req in enumerate(self.pending_requests):
            if req.request_id == request_id:
                if approve:
                    req.is_executed = True
                else:
                    req.is_rejected = True
                self.action_history.append(req)
                return self.pending_requests.pop(idx)
        return None
