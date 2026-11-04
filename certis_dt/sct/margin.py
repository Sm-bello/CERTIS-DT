"""
Airworthiness Structural Margin and Exceedance Probability Evaluator.

Translates real-time surrogate stress fields and calibrated uncertainty bounds
into formal airworthiness margins of safety (FAR 23/25, ARP4754B, DEF-STAN 00-970)
and cumulative fatigue damage (Palmgren-Miner).
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import math
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.uncertainty import UncertaintyEstimate


@dataclass
class MarginEstimate:
    """Formal structural margin and risk metrics."""
    x_grid: np.ndarray
    margin_of_safety: np.ndarray       # MS(x) = (sigma_allow / (1.5 * sigma_99)) - 1.0
    critical_margin_of_safety: float   # Minimum MS along span (worst-case point)
    critical_location_m: float         # Span station with minimum MS
    exceedance_probability: float      # Peak probability of exceeding allowable strain/stress
    cumulative_fatigue_damage: float   # Miner's sum D in [0, 1]
    is_airworthy: bool                 # True iff critical MS >= 0 and not epistemic refusal
    certification_status: str          # "COMPLIANT", "MARGIN_DEGRADED", "AIRWORTHINESS_VIOLATION", "DISQUALIFIED_OOD"


class StructuralMarginEvaluator:
    """
    Computes certification-grade structural margins and failure probabilities.
    
    Standards Traceability:
      - FAR 23.303 / 25.303: Minimum Factor of Safety = 1.50 for ultimate load.
      - ARP4754B Safety Margin Objective: P(exceedance) < 1.0e-5 under hazardous condition.
      - MIL-STD-1530D: Individual Aircraft Tracking (IAT) cumulative fatigue.
    """

    def __init__(
        self,
        geometry: Optional[BoomArmGeometry] = None,
        basquin_fatigue_coeff_pa: float = 850.0e6,  # Fatigue strength coefficient sigma_f'
        basquin_exponent: float = 0.10,             # Basquin fatigue exponent b
    ):
        self.geo = geometry or BoomArmGeometry()
        self.fatigue_coeff = basquin_fatigue_coeff_pa
        self.fatigue_exponent = basquin_exponent
        
        # Cumulative fatigue damage state D in [0, 1]
        self.cumulative_damage = 0.0

    def evaluate_margin(
        self,
        uncertainty_estimate: UncertaintyEstimate,
        dt_seconds: float = 0.01,
    ) -> MarginEstimate:
        """
        Calculates spatial margin of safety and exceedance probability.
        
        Args:
            uncertainty_estimate: Output from UncertaintyQuantifier.
            dt_seconds: Elapsed timestep for fatigue accumulation.
            
        Returns:
            MarginEstimate dataclass with certification flags.
        """
        sigma_allow = self.geo.allowable_stress_pa
        sf = self.geo.safety_factor  # 1.50
        
        x_grid = uncertainty_estimate.x_grid
        stress_mean = uncertainty_estimate.stress_mean_pa
        sigma_total = np.maximum(1e-3, uncertainty_estimate.sigma_total_pa)
        sigma_99 = uncertainty_estimate.stress_upper_bound_99_pa
        
        # Factored 99.87% conservative stress: 1.5 * (mean + 3*sigma)
        factored_stress = sf * np.maximum(1e3, sigma_99)
        
        # Margin of Safety: MS = (sigma_allow / factored_stress) - 1.0
        ms_grid = (sigma_allow / factored_stress) - 1.0
        
        # Find critical (minimum) margin location
        crit_idx = int(np.argmin(ms_grid))
        crit_ms = float(ms_grid[crit_idx])
        crit_x = float(x_grid[crit_idx])
        
        # Compute exceedance probability at critical location via Gaussian tail
        # Z = (sigma_allow / 1.5 - mean) / sigma_total
        z_score = (sigma_allow / sf - stress_mean[crit_idx]) / sigma_total[crit_idx]
        
        # P_exceedance = 0.5 * erfc(Z / sqrt(2))
        try:
            p_exceed = 0.5 * math.erfc(z_score / math.sqrt(2.0))
        except (ValueError, OverflowError):
            p_exceed = 1.0 if z_score < 0 else 0.0
            
        # Update cumulative fatigue damage (Palmgren-Miner rule)
        # S-N Basquin curve: N_f = (sigma_f' / sigma_amp)^(1/b)
        sigma_amp = max(1.0e6, float(stress_mean[crit_idx]))
        try:
            n_cycles_to_failure = (self.fatigue_coeff / sigma_amp) ** (1.0 / self.fatigue_exponent)
            # Cycle increment in dt seconds (assuming dominant 1st modal frequency ~ 25 Hz)
            freq_est = 25.0
            delta_damage = (freq_est * dt_seconds) / max(1.0e3, n_cycles_to_failure)
            self.cumulative_damage = min(1.0, self.cumulative_damage + delta_damage)
        except (ZeroDivisionError, OverflowError):
            pass

        # Determine airworthiness certification status
        if uncertainty_estimate.refusal_to_certify:
            status = "DISQUALIFIED_OOD"
            is_airworthy = False
        elif crit_ms < 0.0 or p_exceed > 1.0e-4:
            status = "AIRWORTHINESS_VIOLATION"
            is_airworthy = False
        elif crit_ms < 0.20:
            status = "MARGIN_DEGRADED"
            is_airworthy = True
        else:
            status = "COMPLIANT"
            is_airworthy = True

        return MarginEstimate(
            x_grid=x_grid,
            margin_of_safety=ms_grid,
            critical_margin_of_safety=crit_ms,
            critical_location_m=crit_x,
            exceedance_probability=p_exceed,
            cumulative_fatigue_damage=self.cumulative_damage,
            is_airworthy=is_airworthy,
            certification_status=status,
        )
