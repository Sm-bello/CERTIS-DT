"""
Structural Component Geometry and Material Specifications.

Defines the physical, structural, and sensor topology for representative UAV
load-bearing airframe components (e.g., carbon-composite boom arm or wing spar).
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import numpy as np


@dataclass(frozen=True)
class SensorStation:
    """Location and orientation of a physical/simulated strain gauge."""
    station_id: str
    normalized_x: float  # Normalized span position x / L in [0, 1]
    surface_z: float     # Distance from neutral axis in meters
    orientation_deg: float = 0.0  # 0.0 = longitudinal bending strain


@dataclass
class BoomArmGeometry:
    """
    Parametric geometry and material model for a high-strength composite/aluminum
    UAV boom arm or wing spar.
    
    Default configuration corresponds to an aerospace-grade carbon fiber/epoxy
    tubular/rectangular boom arm of 0.8m length, suitable for medium-tactical UAVs.
    """
    name: str = "Tactical-UAV-Boom-Arm-CFRP"
    length: float = 0.80             # [m] Total beam length
    outer_width: float = 0.035       # [m] Cross-section outer dimension b
    outer_height: float = 0.035      # [m] Cross-section outer dimension h
    wall_thickness: float = 0.0025   # [m] Wall thickness t
    
    # Material Properties (Aerospace Carbon Fiber Reinforced Polymer / CFRP)
    density: float = 1600.0          # [kg/m^3] Material density
    youngs_modulus: float = 120.0e9  # [Pa] Longitudinal Young's modulus (120 GPa)
    shear_modulus: float = 5.0e9     # [Pa] Shear modulus (5 GPa)
    poisson_ratio: float = 0.30      # [-] Poisson's ratio
    
    # Structural Allowables under Airworthiness Standards (FAR 23/25 / DEF-STAN)
    allowable_stress_pa: float = 650.0e6  # [Pa] Design limit tensile/flexural strength (650 MPa)
    safety_factor: float = 1.5            # [-] Standard airworthiness ultimate safety factor
    
    # Sensor instrumentation stations
    sensor_stations: List[SensorStation] = field(default_factory=lambda: [
        SensorStation(station_id="SG-01", normalized_x=0.10, surface_z=0.0175),
        SensorStation(station_id="SG-02", normalized_x=0.35, surface_z=0.0175),
        SensorStation(station_id="SG-03", normalized_x=0.65, surface_z=0.0175),
    ])

    @property
    def inner_width(self) -> float:
        return max(0.0, self.outer_width - 2.0 * self.wall_thickness)

    @property
    def inner_height(self) -> float:
        return max(0.0, self.outer_height - 2.0 * self.wall_thickness)

    @property
    def cross_section_area(self) -> float:
        """Cross-sectional area A in m^2."""
        return (self.outer_width * self.outer_height) - (self.inner_width * self.inner_height)

    @property
    def second_moment_of_area(self) -> float:
        """Area moment of inertia I_yy about the horizontal neutral axis in m^4."""
        i_outer = (self.outer_width * (self.outer_height ** 3)) / 12.0
        i_inner = (self.inner_width * (self.inner_height ** 3)) / 12.0
        return i_outer - i_inner

    @property
    def mass_per_unit_length(self) -> float:
        """Linear mass density mu in kg/m."""
        return self.density * self.cross_section_area

    @property
    def total_mass(self) -> float:
        """Total component mass in kg."""
        return self.mass_per_unit_length * self.length

    @property
    def bending_rigidity_ei(self) -> float:
        """Flexural rigidity E * I in N*m^2."""
        return self.youngs_modulus * self.second_moment_of_area

    def get_station_locations(self) -> np.ndarray:
        """Returns array of physical x locations [m] for all sensor stations."""
        return np.array([s.normalized_x * self.length for s in self.sensor_stations], dtype=np.float64)

    def allowable_strain(self) -> float:
        """Permissible elastic strain limit (Hooke's law)."""
        return self.allowable_stress_pa / self.youngs_modulus
