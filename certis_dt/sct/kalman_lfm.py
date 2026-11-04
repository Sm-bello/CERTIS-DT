"""
Kalman Filter with Gaussian Process Latent Force Model (GP-LFM).

Augments physical structural modal states with stochastic latent force dynamics
governed by an Ornstein-Uhlenbeck / Gauss-Markov prior. Provides concurrent
state estimation, unmeasured aerodynamic load tracking, and aleatory covariance.
"""

from typing import Dict, Tuple, Optional
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.truth_fem import StructuralTruthFEM


class KalmanLatentForceFilter:
    """
    Augmented State Extended/Linear Kalman Filter with GP Latent Force Model.
    
    State Vector:
      x = [q_1, ..., q_M, qdot_1, ..., qdot_M, u_latent]^T in R^(2M + 1)
      
    where:
      q: Modal displacements
      qdot: Modal velocities
      u_latent: Unknown aerodynamic tip load driven by SDE:
                du = -gamma * u * dt + sigma_w * dW(t)
    """

    def __init__(
        self,
        geometry: Optional[BoomArmGeometry] = None,
        truth_fem: Optional[StructuralTruthFEM] = None,
        num_modes: int = 3,
        dt: float = 0.01,  # 100 Hz estimator loop
        lfm_correlation_time: float = 0.5,  # [s] Correlation time tau = 1/gamma for gusts
        lfm_force_std: float = 25.0,        # [N] Prior standard deviation of gust loads
        sensor_noise_std_microstrain: float = 8.0,  # [mu-epsilon] Strain measurement noise
    ):
        self.geo = geometry or BoomArmGeometry()
        self.truth = truth_fem or StructuralTruthFEM(geometry=self.geo, num_modes=num_modes)
        self.num_modes = num_modes
        self.dt = dt
        self.state_dim = 2 * num_modes + 1
        
        # GP-LFM parameters
        self.gamma = 1.0 / max(1e-3, lfm_correlation_time)
        self.sigma_w = np.sqrt(2.0 * self.gamma) * lfm_force_std  # SDE diffusion coefficient
        
        # Observation noise covariance R (K x K)
        num_sensors = len(self.geo.sensor_stations)
        sigma_sensor = sensor_noise_std_microstrain * 1e-6
        self.R = (sigma_sensor ** 2) * np.eye(num_sensors)
        
        # Build continuous and discrete system matrices
        self._build_filter_matrices()
        self.reset()

    def _build_filter_matrices(self) -> None:
        """Constructs exact analytical discrete state transition F, Q, and H matrices."""
        M = self.num_modes
        N = self.state_dim
        dt = self.dt
        
        # Exact discrete transition matrix F
        self.F = np.zeros((N, N), dtype=np.float64)
        for n in range(M):
            w = self.truth.omegas[n]
            z = self.truth.modal_damping
            wd = w * np.sqrt(max(0.0, 1.0 - (z ** 2)))
            decay = np.exp(-z * w * dt)
            c = np.cos(wd * dt)
            s = np.sin(wd * dt)
            
            f11 = decay * (c + (z * w / wd) * s)
            f12 = decay * (s / wd)
            f21 = -decay * ((w ** 2 / wd) * s)
            f22 = decay * (c - (z * w / wd) * s)
            
            self.F[n, n] = f11
            self.F[n, M + n] = f12
            self.F[M + n, n] = f21
            self.F[M + n, M + n] = f22
            
            # Dynamic coupling to latent aerodynamic force u
            b_n = self.truth.phi_tip[n] / self.truth.modal_masses[n]
            self.F[n, 2 * M] = (b_n / (w ** 2)) * (1.0 - f11)
            self.F[M + n, 2 * M] = -(b_n / (w ** 2)) * f21
            
        # Latent force state transition: u_{k+1} = exp(-gamma * dt) * u_k
        self.F[2 * M, 2 * M] = np.exp(-self.gamma * dt)
        
        # Process noise matrix Q
        # Latent force diffusion q_spectral = sigma_w^2
        q_spectral = self.sigma_w ** 2
        self.Q = np.zeros((N, N), dtype=np.float64)
        self.Q[:M, :M] = 1e-10 * np.eye(M)
        self.Q[M:2*M, M:2*M] = 1e-6 * np.eye(M)
        self.Q[2 * M, 2 * M] = q_spectral * dt
        
        # Measurement matrix H: maps modal coordinates q to sensor strains y
        z_outer = self.geo.outer_height / 2.0
        K = len(self.geo.sensor_stations)
        self.H = np.zeros((K, N), dtype=np.float64)
        self.H[:, :M] = -z_outer * self.truth.phi_d2_sensors[:, :M]

    def reset(self) -> None:
        """Reset state vector and covariance."""
        self.x_hat = np.zeros(self.state_dim, dtype=np.float64)
        # Initial covariance
        self.P = np.diag(
            [1e-6] * self.num_modes + [1e-4] * self.num_modes + [100.0]
        )
        self.last_innovation = np.zeros(len(self.geo.sensor_stations))
        self.last_innovation_cov = np.copy(self.R)

    def predict(self) -> None:
        """Time update step: x_{k|k-1} = F * x_{k-1|k-1}, P_{k|k-1} = F * P * F^T + Q."""
        self.x_hat = self.F @ self.x_hat
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, measurement: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Measurement update step.
        
        Args:
            measurement: Measured strain gauge telemetry y_k (length K).
            
        Returns:
            Dictionary containing estimated state, latent force, innovation, and uncertainty.
        """
        y = np.asarray(measurement, dtype=np.float64)
        
        # Innovation residual: r = y - H * x_pred
        y_pred = self.H @ self.x_hat
        residual = y - y_pred
        self.last_innovation = residual
        
        # Innovation covariance: S = H * P * H^T + R
        S = self.H @ self.P @ self.H.T + self.R
        self.last_innovation_cov = S
        
        # Robust pseudo-inverse / solve for Kalman Gain
        try:
            S_inv = np.linalg.pinv(S)
            K = self.P @ self.H.T @ S_inv
        except Exception:
            K = np.zeros((self.state_dim, len(y)))
        
        # Corrected state: x_hat = x_pred + K * r
        self.x_hat = self.x_hat + K @ residual
        
        # Corrected covariance (Joseph form for numerical symmetry & positive-definiteness)
        I_KH = np.eye(self.state_dim) - K @ self.H
        self.P = I_KH @ self.P @ I_KH.T + K @ self.R @ K.T
        
        # Extract estimated modal coordinates and estimated latent load
        q_est = self.x_hat[:self.num_modes]
        qdot_est = self.x_hat[self.num_modes:2*self.num_modes]
        latent_force_est = float(self.x_hat[2*self.num_modes])
        latent_force_std = float(np.sqrt(max(0.0, self.P[2*self.num_modes, 2*self.num_modes])))
        
        # Modal covariance matrix (M x M)
        P_qq = self.P[:self.num_modes, :self.num_modes]

        return {
            "q_est": q_est,
            "qdot_est": qdot_est,
            "latent_force_n": latent_force_est,
            "latent_force_std_n": latent_force_std,
            "innovation": residual,
            "innovation_cov": S,
            "modal_cov": P_qq,
            "state_vector": np.copy(self.x_hat),
        }
