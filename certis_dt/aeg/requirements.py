"""
Airworthiness Requirements Taxonomy and Standards Mapping.

Formalizes requirement templates aligned with ARP4754B, DO-178C (DAL B),
EASA AI Roadmap 2.0 (Level 2), and MIL-STD-1530D (ASIP).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class StandardAuthority(Enum):
    ARP4754B = "ARP4754B"        # Guidelines for Development of Civil Aircraft and Systems
    DO178C = "DO178C"            # Software Considerations in Airborne Systems (DAL B)
    EASA_AI_L2 = "EASA_AI_L2"    # EASA AI Roadmap 2.0 Human-AI Teaming
    MIL_STD_1530D = "MIL_STD_1530D" # Aircraft Structural Integrity Program (ASIP)
    FAA_PART23 = "FAA_PART23"    # Airworthiness Standards: Normal Category Airplanes


class RequirementStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    REFUSED_OOD = "REFUSED_OOD"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass
class AirworthinessRequirement:
    req_id: str
    standard: StandardAuthority
    title: str
    description: str
    dal_level: str               # "DAL A", "DAL B", "DAL C"
    threshold_expression: str
    verification_method: str      # "Analysis", "Simulation Test", "Inspection"
    current_status: RequirementStatus = RequirementStatus.NOT_EVALUATED
    evidence_summary: str = ""


class AirworthinessRequirementsRegistry:
    """
    Standard repository of airworthiness objectives for the CERTIS-DT testbed.
    """

    @classmethod
    def get_baseline_requirements(cls) -> Dict[str, AirworthinessRequirement]:
        """Returns foundational aerospace certification requirements."""
        reqs = [
            AirworthinessRequirement(
                req_id="REQ-STRUCT-001",
                standard=StandardAuthority.FAA_PART23,
                title="Ultimate Structural Margin of Safety",
                description="Airframe component shall sustain limit load times ultimate factor of safety (1.50) with non-negative margin of safety (MS >= 0.0) at 99.87% confidence.",
                dal_level="DAL B",
                threshold_expression="critical_margin_of_safety >= 0.0",
                verification_method="Analysis & Structural Surrogate UQ",
            ),
            AirworthinessRequirement(
                req_id="REQ-STRUCT-002",
                standard=StandardAuthority.MIL_STD_1530D,
                title="Cumulative Fatigue Damage Tracking",
                description="Cumulative fatigue damage index D under operational load spectra shall not exceed allowable service life fraction (D <= 0.80).",
                dal_level="DAL B",
                threshold_expression="cumulative_damage <= 0.80",
                verification_method="Continuous Palmgren-Miner IAT Monitoring",
            ),
            AirworthinessRequirement(
                req_id="REQ-SWARM-001",
                standard=StandardAuthority.ARP4754B,
                title="Virtual-Physical State Synchronization Bound",
                description="The virtual twin state shall track physical UAV positions within an airworthiness corridor of RMSE <= 0.20m under nominal communication links.",
                dal_level="DAL B",
                threshold_expression="mean_position_rmse_m <= 0.20",
                verification_method="Simulation Telemetry Analysis",
            ),
            AirworthinessRequirement(
                req_id="REQ-SWARM-002",
                standard=StandardAuthority.ARP4754B,
                title="Bidirectional Synchronization Latency",
                description="Bidirectional state telemetry and command transfer latency shall exhibit 95th percentile latency <= 50 ms.",
                dal_level="DAL B",
                threshold_expression="p95_latency_ms <= 50.0",
                verification_method="Tactical Network Channel Benchmarking",
            ),
            AirworthinessRequirement(
                req_id="REQ-AI-001",
                standard=StandardAuthority.EASA_AI_L2,
                title="Epistemic Out-Of-Distribution Gating",
                description="Surrogate AI/estimation models shall detect out-of-distribution operating conditions via Mahalanobis innovation gating and refuse to emit unverified flight claims.",
                dal_level="DAL B",
                threshold_expression="epistemic_credibility >= 0.25 and not is_out_of_distribution",
                verification_method="Statistical Hypothesis Testing",
            ),
            AirworthinessRequirement(
                req_id="REQ-AI-002",
                standard=StandardAuthority.EASA_AI_L2,
                title="Explainability-by-Construction for Safety Actions",
                description="Every autonomous structural reconfiguration or mission abort directive shall emit a causal attribution docket for Human-On-The-Loop review.",
                dal_level="DAL B",
                threshold_expression="has_causal_explanation == True",
                verification_method="Automated Docket Inspection",
            ),
            AirworthinessRequirement(
                req_id="REQ-SW-001",
                standard=StandardAuthority.DO178C,
                title="Deterministic Surrogate Execution Deadline",
                description="Structural surrogate inference execution time shall deterministically complete in <= 2.0 ms per evaluation epoch.",
                dal_level="DAL B",
                threshold_expression="execution_time_us <= 2000.0",
                verification_method="Worst-Case Execution Time (WCET) Timing Analysis",
            ),
        ]
        return {r.req_id: r for r in reqs}
