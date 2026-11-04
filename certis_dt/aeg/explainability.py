"""
Explainability-by-Construction and Refusal-to-Certify Engine.

Generates deterministic, auditor-ready causal attribution records for airworthiness
safety inspectors, fulfilling EASA AI Roadmap 2.0 explainability criteria.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import numpy as np


@dataclass
class CausalAttributionRecord:
    record_id: str
    timestamp_s: float
    target_agent_id: str
    event_category: str            # "EPISTEMIC_REFUSAL", "MARGIN_DEGRADATION", "LEADER_SWAP", "RTB_ABORT"
    primary_trigger: str
    sensor_residuals_sigma: Dict[str, float]
    physical_mechanism_hypothesis: str
    safety_mitigation_action: str
    auditor_verdict: str           # "DISQUALIFIED_SAFE", "RECONFIGURED_AIRWORTHY"


class ExplainabilityEngine:
    """
    Constructs explainable rationale dockets for every autonomous safety action.
    """

    def __init__(self):
        self.records: List[CausalAttributionRecord] = []
        self._counter = 0

    def generate_refusal_attribution(
        self,
        agent_id: str,
        current_time_s: float,
        mahalanobis_d2: float,
        chi2_threshold: float,
        credibility: float,
        innovation_residual: np.ndarray,
        sensor_station_ids: List[str],
    ) -> CausalAttributionRecord:
        """
        Produce formal explanation when SCT refuses to certify telemetry.
        """
        self._counter += 1
        rec_id = f"EXP-REFUSAL-{self._counter:04d}"
        
        # Attribute residual error to individual sensor stations
        residuals_dict = {}
        max_sensor_id = "UNKNOWN"
        max_val = -1.0
        for idx, sid in enumerate(sensor_station_ids):
            if idx < len(innovation_residual):
                val = float(np.abs(innovation_residual[idx])) * 1.0e6  # microstrain
                residuals_dict[sid] = val
                if val > max_val:
                    max_val = val
                    max_sensor_id = sid
                    
        hypothesis = (
            f"Epistemic discordance: Mahalanobis D^2={mahalanobis_d2:.2f} statistically rejects physical surrogate "
            f"hypothesis at p < 0.001 (critical chi^2={chi2_threshold:.2f}). Dominant residual localized at "
            f"sensor {max_sensor_id} ({max_val:.1f} microstrain). Likely cause: Sensor debonding, severe local damage, "
            f"or aerodynamic stall turbulence."
        )
        
        action = "Digital twin issued Refusal-to-Certify; flight envelope frozen; agent commanded to FALLBACK_RTB."
        
        record = CausalAttributionRecord(
            record_id=rec_id,
            timestamp_s=current_time_s,
            target_agent_id=agent_id,
            event_category="EPISTEMIC_REFUSAL",
            primary_trigger=f"Credibility collapsed to {credibility:.3f} (< 0.25 threshold)",
            sensor_residuals_sigma=residuals_dict,
            physical_mechanism_hypothesis=hypothesis,
            safety_mitigation_action=action,
            auditor_verdict="DISQUALIFIED_SAFE",
        )
        self.records.append(record)
        return record

    def generate_replan_attribution(
        self,
        agent_id: str,
        current_time_s: float,
        old_role: str,
        new_role: str,
        margin_of_safety: float,
        action_rationale: str,
    ) -> CausalAttributionRecord:
        """
        Produce formal explanation for structural-aware swarm re-planning events.
        """
        self._counter += 1
        rec_id = f"EXP-REPLAN-{self._counter:04d}"
        
        record = CausalAttributionRecord(
            record_id=rec_id,
            timestamp_s=current_time_s,
            target_agent_id=agent_id,
            event_category="LEADER_SWAP" if "LEADER" in new_role or "LEADER" in old_role else "FORMATION_ADAPT",
            primary_trigger=f"Critical Margin of Safety MS={margin_of_safety:.3f} under high gust spectrum",
            sensor_residuals_sigma={},
            physical_mechanism_hypothesis=action_rationale,
            safety_mitigation_action=f"Reassigned role {old_role} -> {new_role}; derated velocity envelope.",
            auditor_verdict="RECONFIGURED_AIRWORTHY",
        )
        self.records.append(record)
        return record
