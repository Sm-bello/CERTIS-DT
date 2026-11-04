"""
Airworthiness Evidence Generator (AEG) Module.

Synthesizes certification evidence compliant with ARP4754B, DO-178C (DAL B),
EASA AI Roadmap 2.0 (Level 2), and MIL-STD-1530D, utilizing Goal Structuring
Notation (GSN) / SACM metamodels and explainability-by-construction gating.
"""

from certis_dt.aeg.requirements import (
    StandardAuthority,
    RequirementStatus,
    AirworthinessRequirement,
    AirworthinessRequirementsRegistry,
)
from certis_dt.aeg.gsn import GSNAssuranceCase, GSNNode, GSNNodeType, GSNStatus
from certis_dt.aeg.evidence_collector import EvidenceCollector
from certis_dt.aeg.explainability import ExplainabilityEngine, CausalAttributionRecord
from certis_dt.aeg.docket_exporter import CertificationDocketExporter

__all__ = [
    "StandardAuthority",
    "RequirementStatus",
    "AirworthinessRequirement",
    "AirworthinessRequirementsRegistry",
    "GSNAssuranceCase",
    "GSNNode",
    "GSNNodeType",
    "GSNStatus",
    "EvidenceCollector",
    "ExplainabilityEngine",
    "CausalAttributionRecord",
    "CertificationDocketExporter",
]
