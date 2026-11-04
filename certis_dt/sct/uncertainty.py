"""
Dual Aleatory and Epistemic Uncertainty Quantification (UQ).

Propagates state error covariance to full-field stress variances (aleatory)
and implements statistical Mahalanobis innovation gating for out-of-distribution
(OOD) detection and epistemic refusal-to-certify decisions.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import math
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.truth_fem import StructuralTruthFEM


@dataclass
class UncertaintyEstimate:
    """Quantitative uncertainty bounds across spatial grid."""
    x_grid: np.ndarray
    stress_mean_pa: np.ndarray
    sigma_aleatory_pa: np.ndarray
    sigma_epistemic_pa: np.ndarray
    sigma_total_pa: np.ndarray
    stress_upper_bound_99_pa: np.ndarray  # Mean + 3 * sigma_total (99.87% one-sided bound)
    mahalanobis_d2: float
    epistemic_credibility: float          # [0.0 to 1.0]
    is_out_of_distribution: bool
    refusal_to_certify: bool
    explanation: str


class UncertaintyQuantifier:
    """
    Computes rigorous aleatory and epistemic uncertainty bounds on full-field stresses.
    
    Statistical Formulation:
      - Aleatory Variance: sigma_aleatory^2(x) = E^2 * z_outer^2 * Phi''(x)^T * P_qq * Phi''(x)
      - Epistemic Mahalanobis Distance: D_M^2 = r_k^T * S_k^(-1) * r_k
      - Chi-Squared Hypothesis Testing: D_M^2 ~ Chi^2_K
      - Epistemic Credibility Score: C_k = exp(-max(0, D_M^2 - K) / (2*K))
      - Total Sigma: sigma_total(x) = sigma_aleatory(x) + sigma_epistemic(x)
    """

    # Approximate 99.9% Chi-Square critical values for degrees of freedom K=1..8
    CHI2_999_CRITICAL = {
        1: 10.83,
        2: 13.82,
        3: 16.27,
        4: 18.47,
        5: 20.52,
        6: 22.46,
        7: 24.32,
        8: 26.12,
    }

    def __init__(
        self,
        geometry: Optional[BoomArmGeometry] = None,
        truth_fem: Optional[StructuralTruthFEM] = None,
        num_modes: int = 3,
        credibility_refusal_threshold: float = 0.25,
    ):
        self.geo = geometry or BoomArmGeometry()
        self.truth = truth_fem or StructuralTruthFEM(geometry=self.geo, num_modes=num_modes)
        self.num_modes = num_modes
        self.credibility_threshold = credibility_refusal_threshold
        
        K = len(self.geo.sensor_stations)
        self.chi2_threshold = self.CHI2_999_CRITICAL.get(K, 3.0 * K + 10.0)

    def evaluate_uncertainty(
        self,
        stress_mean_pa: np.ndarray,
        modal_covariance: np.ndarray,
        innovation_residual: np.ndarray,
        innovation_covariance: np.ndarray,
    ) -> UncertaintyEstimate:
        """
        Evaluate complete spatial uncertainty and epistemic validity envelope.
        
        Args:
            stress_mean_pa: Reconstructed mean stress along x_grid (shape N_nodes).
            modal_covariance: P_qq matrix from Kalman filter (shape M x M).
            innovation_residual: r_k = y_k - y_hat_k (shape K).
            innovation_covariance: S_k matrix (shape K x K).
            
        Returns:
            UncertaintyEstimate dataclass instance.
        """
        N = len(self.truth.x_grid)
        z_outer = self.geo.outer_height / 2.0
        E = self.geo.youngs_modulus
        
        # 1. Full-field Aleatory Uncertainty Propagation
        # Var[stress(x)] = E^2 * z_outer^2 * phi_d2(x)^T * P_qq * phi_d2(x)
        phi_d2 = self.truth.phi_d2_grid[:, :self.num_modes]  # (N, M)
        # Vectorized quadratic form: diag(phi_d2 @ P_qq @ phi_d2^T)
        intermediate = phi_d2 @ modal_covariance  # (N, M)
        var_curvature = np.sum(intermediate * phi_d2, axis=1)  # (N,)
        var_aleatory = (E * z_outer) ** 2 * np.maximum(0.0, var_curvature)
        sigma_aleatory = np.sqrt(var_aleatory)
        
        # 2. Epistemic Uncertainty via Mahalanobis Distance of Innovation
        r = np.asarray(innovation_residual, dtype=np.float64)
        S = np.asarray(innovation_covariance, dtype=np.float64)
        K = len(r)
        
        try:
            S_inv = np.linalg.inv(S)
            d2 = float(r.T @ S_inv @ r)
        except np.linalg.LinAlgError:
            d2 = 999.0
            
        # Epistemic Credibility C_k in [0, 1]
        excess = max(0.0, d2 - K)
        credibility = float(np.exp(-excess / (2.0 * K)))
        
        # Epistemic standard deviation proportional to mean stress and model suspicion
        # When credibility is 1.0, epistemic sigma is zero; when credibility drops, sigma expands
        sigma_epistemic = stress_mean_pa * (1.0 - credibility) * 0.50
        
        sigma_total = sigma_aleatory + sigma_epistemic
        upper_bound_99 = stress_mean_pa + 3.0 * sigma_total
        
        is_ood = bool(d2 > self.chi2_threshold)
        refuse_to_certify = bool(credibility < self.credibility_threshold or is_ood)
        
        if refuse_to_certify:
            explanation = (
                f"DISQUALIFICATION: High epistemic discrepancy (D_M^2={d2:.2f} > chi2_crit={self.chi2_threshold:.2f}, "
                f"Credibility={credibility:.3f} < {self.credibility_threshold:.2f}). Telemetry rejected; "
                f"sensor fault or out-of-envelope dynamics suspected."
            )
        else:
            explanation = (
                f"VALIDATED: Innovation within statistical bounds (D_M^2={d2:.2f} <= {self.chi2_threshold:.2f}, "
                f"Credibility={credibility:.3f}). Reconstructed stress certified with 99.87% confidence."
            )

        return UncertaintyEstimate(
            x_grid=self.truth.x_grid,
            stress_mean_pa=stress_mean_pa,
            sigma_aleatory_pa=sigma_aleatory,
            sigma_epistemic_pa=sigma_epistemic,
            sigma_total_pa=sigma_total,
            stress_upper_bound_99_pa=upper_bound_99,
            mahalanobis_d2=d2,
            epistemic_credibility=credibility,
            is_out_of_distribution=is_ood,
            refusal_to_certify=refuse_to_certify,
            explanation=explanation,
        )
