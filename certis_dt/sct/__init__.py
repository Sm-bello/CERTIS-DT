"""
Structural Certification Twin (SCT) Module.

Provides physics-based finite element truth dynamics, real-time modal/unit-load
surrogates, Kalman Filter with Gaussian Process Latent Force Models (GP-LFM),
dual aleatory/epistemic uncertainty quantification, and airworthiness margin calculation.
"""

from certis_dt.sct.geometry import BoomArmGeometry, SensorStation
from certis_dt.sct.truth_fem import StructuralTruthFEM
from certis_dt.sct.surrogate import StructuralSurrogate
from certis_dt.sct.kalman_lfm import KalmanLatentForceFilter
from certis_dt.sct.uncertainty import UncertaintyQuantifier, UncertaintyEstimate
from certis_dt.sct.margin import StructuralMarginEvaluator, MarginEstimate

__all__ = [
    "BoomArmGeometry",
    "SensorStation",
    "StructuralTruthFEM",
    "StructuralSurrogate",
    "KalmanLatentForceFilter",
    "UncertaintyQuantifier",
    "UncertaintyEstimate",
    "StructuralMarginEvaluator",
    "MarginEstimate",
]
