"""
High-Fidelity Physics Truth Model for Beam Dynamics.

Implements modal superposition dynamic equations for a cantilever structural
component under time-varying tip loads (propeller thrust/torque) and distributed
aerodynamic gust loads. Serves as ground-truth for surrogate and estimator benchmarking.
"""

from typing import List, Tuple, Optional, Dict
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry, SensorStation


class StructuralTruthFEM:
    """
    Continuous modal dynamics truth model for an aerospace cantilever spar/boom arm.
    
    Governing differential equation:
      mu * d^2 w(x,t)/dt^2 + c * dw(x,t)/dt + EI * d^4 w(x,t)/dx^4 = p(x,t) + F_tip(t)*delta(x-L)
    
    Uses orthogonal modal expansion:
      w(x,t) = sum_{n=1}^N q_n(t) * phi_n(x)
      epsilon(x,t) = -z * sum_{n=1}^N q_n(t) * phi''_n(x)
    """

    # Roots beta_n * L of transcendental equation cos(beta*L)*cosh(beta*L) + 1 = 0
    CANTILEVER_BETA_L = np.array([1.87510407, 4.69409113, 7.85475744, 10.99554073, 14.13716839], dtype=np.float64)

    def __init__(
        self,
        geometry: Optional[BoomArmGeometry] = None,
        num_modes: int = 4,
        modal_damping: float = 0.015,  # 1.5% modal damping ratio (typical CFRP)
        spatial_nodes: int = 100,
    ):
        self.geo = geometry or BoomArmGeometry()
        self.num_modes = min(num_modes, len(self.CANTILEVER_BETA_L))
        self.modal_damping = modal_damping
        self.spatial_nodes = spatial_nodes
        
        # Discretized spatial grid along beam length x in [0, L]
        self.x_grid = np.linspace(0.0, self.geo.length, self.spatial_nodes, dtype=np.float64)
        
        # Compute modal parameters
        self._compute_modal_basis()
        
        # State vector: [q_1..q_N, qdot_1..qdot_N]
        self.q = np.zeros(self.num_modes, dtype=np.float64)
        self.q_dot = np.zeros(self.num_modes, dtype=np.float64)
        self.time = 0.0

    def _compute_modal_basis(self) -> None:
        """Computes beta_n, omega_n, modal mass, and basis functions over x_grid."""
        L = self.geo.length
        EI = self.geo.bending_rigidity_ei
        mu = self.geo.mass_per_unit_length
        
        self.betas = self.CANTILEVER_BETA_L[:self.num_modes] / L
        # Natural frequencies [rad/s] and [Hz]
        self.omegas = (self.betas ** 2) * np.sqrt(EI / mu)
        self.freqs_hz = self.omegas / (2.0 * np.pi)
        
        # Alpha coefficients for mode shapes
        cosh_bL = np.cosh(self.betas * L)
        cos_bL = np.cos(self.betas * L)
        sinh_bL = np.sinh(self.betas * L)
        sin_bL = np.sin(self.betas * L)
        self.alphas = (cosh_bL + cos_bL) / (sinh_bL + sin_bL)
        
        # Precompute mode shape matrices on x_grid: shape (spatial_nodes, num_modes)
        self.phi_grid = np.zeros((self.spatial_nodes, self.num_modes), dtype=np.float64)
        self.phi_d2_grid = np.zeros((self.spatial_nodes, self.num_modes), dtype=np.float64)
        
        for n in range(self.num_modes):
            bx = self.betas[n] * self.x_grid
            a = self.alphas[n]
            # Displacement mode shape phi_n(x)
            self.phi_grid[:, n] = np.cosh(bx) - np.cos(bx) - a * (np.sinh(bx) - np.sin(bx))
            # Curvature mode shape phi''_n(x)
            self.phi_d2_grid[:, n] = (self.betas[n] ** 2) * (
                np.cosh(bx) + np.cos(bx) - a * (np.sinh(bx) + np.sin(bx))
            )
            
        # Modal masses M_n = int_0^L mu * phi_n^2(x) dx
        # For normalized cantilever modes, int phi_n^2 dx = L
        self.modal_masses = mu * self.geo.length * np.ones(self.num_modes, dtype=np.float64)
        
        # Sensor station coordinates and basis values
        self.sensor_x = self.geo.get_station_locations()
        num_sensors = len(self.sensor_x)
        self.phi_d2_sensors = np.zeros((num_sensors, self.num_modes), dtype=np.float64)
        
        for s_idx, station in enumerate(self.geo.sensor_stations):
            bx = self.betas * (station.normalized_x * L)
            self.phi_d2_sensors[s_idx, :] = (self.betas ** 2) * (
                np.cosh(bx) + np.cos(bx) - self.alphas * (np.sinh(bx) + np.sin(bx))
            )
            
        # Tip displacement mode values phi_n(L)
        bL = self.betas * L
        self.phi_tip = np.cosh(bL) - np.cos(bL) - self.alphas * (np.sinh(bL) - np.sin(bL))

    def reset(self) -> None:
        """Reset state to rest."""
        self.q.fill(0.0)
        self.q_dot.fill(0.0)
        self.time = 0.0

    def step(
        self,
        dt: float,
        tip_force_n: float,
        distributed_load_npm: float = 0.0,
    ) -> Dict[str, np.ndarray]:
        """
        Advance dynamic simulation by dt using unconditionally stable, exact analytical modal propagation.
        
        For each decoupled mode:
          q_ddot + 2*zeta*omega*q_dot + omega^2*q = f_n
          
        Args:
            dt: Timestep in seconds.
            tip_force_n: Vertical tip load in Newtons (propeller thrust/maneuver load).
            distributed_load_npm: Uniform aero gust load along span in N/m.
            
        Returns:
            Dictionary containing ground-truth full-field deflection, strain, and stress.
        """
        dist_integral = 2.0 * self.alphas / self.betas
        Q = tip_force_n * self.phi_tip + distributed_load_npm * dist_integral
        
        for n in range(self.num_modes):
            w_n = self.omegas[n]
            zeta_n = self.modal_damping
            m_n = self.modal_masses[n]
            f_n = Q[n] / m_n
            
            wd = w_n * np.sqrt(max(0.0, 1.0 - zeta_n ** 2))
            q_stat = f_n / (w_n ** 2)
            q_dev = self.q[n] - q_stat
            decay = np.exp(-zeta_n * w_n * dt)
            cos_w = np.cos(wd * dt)
            sin_w = np.sin(wd * dt)
            
            q_next = q_stat + decay * (q_dev * cos_w + (self.q_dot[n] + zeta_n * w_n * q_dev) / wd * sin_w)
            qdot_next = decay * (
                self.q_dot[n] * cos_w
                - (wd + ((zeta_n * w_n) ** 2) / wd) * q_dev * sin_w
                - (zeta_n * w_n * self.q_dot[n] / wd) * sin_w
            )
            
            self.q[n] = q_next
            self.q_dot[n] = qdot_next
            
        self.time += dt
        return self.get_full_field_truth()

    def get_full_field_truth(self) -> Dict[str, np.ndarray]:
        """Calculates exact continuous deflection, curvature, strain, and stress along x_grid."""
        z_outer = self.geo.outer_height / 2.0
        
        # Deflection w(x) = sum q_n * phi_n(x)
        deflection_m = self.phi_grid @ self.q
        
        # Curvature kappa(x) = sum q_n * phi''_n(x)
        curvature = self.phi_d2_grid @ self.q
        
        # Longitudinal bending strain epsilon_xx(x, z_outer) = -z * kappa
        strain_xx = -z_outer * curvature
        
        # Bending stress sigma_xx(x) = E * epsilon_xx(x)
        stress_pa = self.geo.youngs_modulus * np.abs(strain_xx)
        
        # Bending moment M(x) = EI * kappa(x)
        bending_moment_nm = self.geo.bending_rigidity_ei * np.abs(curvature)

        return {
            "x_grid": self.x_grid,
            "deflection_m": deflection_m,
            "curvature": curvature,
            "strain_xx": strain_xx,
            "stress_pa": stress_pa,
            "bending_moment_nm": bending_moment_nm,
            "tip_deflection_m": float(np.dot(self.phi_tip, self.q)),
            "max_stress_pa": float(np.max(stress_pa)),
            "time_s": self.time,
        }

    def measure_strains(
        self,
        noise_std_microstrain: float = 5.0,
        sensor_fault_mask: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Simulate sparse strain gauge telemetry.
        
        Args:
            noise_std_microstrain: Gaussian sensor noise standard deviation in microstrain (mu-epsilon).
            sensor_fault_mask: Dictionary mapping station_id to scale/drift factor (for fault injection).
            
        Returns:
            1D array of strain readings in raw strain (m/m) for each sensor station.
        """
        z_outer = self.geo.outer_height / 2.0
        # True strains at sensor locations: -z * phi''_sensors @ q
        curvatures = self.phi_d2_sensors @ self.q
        true_strains = -z_outer * curvatures
        
        noise = np.random.normal(0.0, noise_std_microstrain * 1e-6, size=len(true_strains))
        measured = true_strains + noise
        
        # Apply fault injection if requested
        if sensor_fault_mask:
            for idx, station in enumerate(self.geo.sensor_stations):
                if station.station_id in sensor_fault_mask:
                    factor = sensor_fault_mask[station.station_id]
                    measured[idx] *= factor

        return measured
