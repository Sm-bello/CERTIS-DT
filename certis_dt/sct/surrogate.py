"""
Real-Time Structural Surrogate Model.

Provides sub-millisecond sparse-to-full-field reconstruction of strain and stress
tensors using precomputed modal/unit-load basis projection and regularized
inverse sensing kernels. Compliant with DO-178C deterministic execution constraints.
"""

from typing import Dict, Tuple, Optional
import time
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.truth_fem import StructuralTruthFEM


class StructuralSurrogate:
    """
    Sub-millisecond structural surrogate for full-field stress and strain reconstruction.
    
    Mathematical Formulation:
      Sensor Strain: y = H_sens * q + v
      Reconstructed Modal Coordinates: q_hat = W_inv * y
      Full-Field Curvature: kappa_hat(x) = Phi''_grid * q_hat = (Phi''_grid * W_inv) * y
      Full-Field Stress: sigma_hat(x) = E * z_outer * |K_rec * y|
      
    where K_rec = Phi''_grid * (H_sens^T * H_sens + lambda * I)^(-1) * H_sens^T
    is precomputed offline, rendering online evaluation O(N_nodes * K_sensors) flops (< 20 us).
    """

    def __init__(
        self,
        geometry: Optional[BoomArmGeometry] = None,
        truth_fem: Optional[StructuralTruthFEM] = None,
        num_modes: int = 3,
        regularization_lambda: float = 1e-7,
        spatial_nodes: int = 100,
    ):
        self.geo = geometry or BoomArmGeometry()
        self.truth = truth_fem or StructuralTruthFEM(geometry=self.geo, num_modes=num_modes, spatial_nodes=spatial_nodes)
        self.num_modes = num_modes
        self.regularization_lambda = regularization_lambda
        self.spatial_nodes = spatial_nodes
        self.x_grid = self.truth.x_grid
        
        # Build precomputed deterministic reconstruction kernels
        self._build_reconstruction_kernel()

    def _build_reconstruction_kernel(self) -> None:
        """Precomputes the inverse sensor mapping and full-field reconstruction matrices."""
        z_outer = self.geo.outer_height / 2.0
        
        # Sensor measurement matrix H_sens: maps modal coordinates q (shape M) to sensor strains y (shape K)
        # y_sens = -z_outer * phi_d2_sensors @ q
        self.H_sens = -z_outer * self.truth.phi_d2_sensors[:, :self.num_modes]  # shape (K, M)
        
        # Regularized pseudo-inverse W_inv = (H^T * H + lambda * I)^(-1) * H^T
        HtH = self.H_sens.T @ self.H_sens  # (M, M)
        reg_matrix = HtH + self.regularization_lambda * np.eye(self.num_modes)
        self.W_inv = np.linalg.solve(reg_matrix, self.H_sens.T)  # (M, K)
        
        # Full-field curvature matrix Phi''_grid: shape (N_nodes, M)
        phi_d2 = self.truth.phi_d2_grid[:, :self.num_modes]
        
        # Precomputed linear reconstruction kernel K_rec: shape (N_nodes, K)
        # kappa_grid = K_rec @ y_sens
        self.K_rec = phi_d2 @ self.W_inv  # (N_nodes, K)
        
        # Full-field displacement matrix
        phi = self.truth.phi_grid[:, :self.num_modes]
        self.K_disp = phi @ self.W_inv  # (N_nodes, K)

    def reconstruct(self, sensor_strains: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Reconstruct full-field deflection, strain, and stress from sparse strain gauge telemetry.
        
        Args:
            sensor_strains: 1D array of length K with measured strains (m/m).
            
        Returns:
            Dictionary containing:
              - x_grid: spatial coordinates [m]
              - deflection_m: reconstructed vertical deflection [m]
              - strain_xx: reconstructed bending strain tensor [m/m]
              - stress_pa: reconstructed von Mises/bending stress [Pa]
              - max_stress_pa: peak reconstructed stress [Pa]
              - execution_time_us: inference execution latency in microseconds
              - modal_q_hat: estimated modal coordinates
        """
        t_start = time.perf_counter()
        
        y = np.asarray(sensor_strains, dtype=np.float64)
        z_outer = self.geo.outer_height / 2.0
        
        # Estimated modal state
        q_hat = self.W_inv @ y
        
        # Full-field curvature kappa_hat(x)
        curvature_hat = self.K_rec @ y
        
        # Strain and stress
        strain_hat = -z_outer * curvature_hat
        stress_hat = self.geo.youngs_modulus * np.abs(strain_hat)
        
        # Deflection
        deflection_hat = self.K_disp @ y
        
        t_end = time.perf_counter()
        dt_us = (t_end - t_start) * 1.0e6
        
        return {
            "x_grid": self.x_grid,
            "deflection_m": deflection_hat,
            "strain_xx": strain_hat,
            "stress_pa": stress_hat,
            "max_stress_pa": float(np.max(stress_hat)),
            "modal_q_hat": q_hat,
            "execution_time_us": dt_us,
        }
