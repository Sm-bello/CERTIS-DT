"""
Hardware-In-The-Loop (HIL) and Fault Injection Module.

Provides realistic cyber-physical fault injection capabilities and end-to-end
TRL 5 mission simulation harnesses for airworthiness degradation evaluation.
"""

from certis_dt.hil.fault_injector import FaultInjector, FaultProfile, FaultMode
from certis_dt.hil.trl5_evaluator import TRL5MissionHarness, MissionSimulationResult

__all__ = [
    "FaultInjector",
    "FaultProfile",
    "FaultMode",
    "TRL5MissionHarness",
    "MissionSimulationResult",
]
