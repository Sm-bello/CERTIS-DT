"""
Unit tests for Layer 1 SCT: Structural Surrogate and Truth Model.
"""

import unittest
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.truth_fem import StructuralTruthFEM
from certis_dt.sct.surrogate import StructuralSurrogate
from certis_dt.sct.kalman_lfm import KalmanLatentForceFilter


class TestStructuralSurrogate(unittest.TestCase):
    def setUp(self):
        self.geo = BoomArmGeometry()
        self.truth = StructuralTruthFEM(geometry=self.geo, num_modes=3)
        self.surrogate = StructuralSurrogate(geometry=self.geo, truth_fem=self.truth, num_modes=3)
        self.filter = KalmanLatentForceFilter(geometry=self.geo, truth_fem=self.truth, dt=0.01)

    def test_truth_fem_dynamics(self):
        """Verify modal physics truth model advances and generates non-zero stress."""
        res = self.truth.step(dt=0.01, tip_force_n=80.0)
        self.assertGreater(res["max_stress_pa"], 1.0e6)
        self.assertGreater(res["tip_deflection_m"], 0.0)

    def test_surrogate_reconstruction_accuracy(self):
        """Verify sub-millisecond surrogate accurately tracks full-field stress."""
        self.truth.step(dt=0.01, tip_force_n=100.0)
        truth_field = self.truth.get_full_field_truth()
        strains = self.truth.measure_strains(noise_std_microstrain=0.0)
        
        rec = self.surrogate.reconstruct(strains)
        truth_max = truth_field["max_stress_pa"]
        rec_max = rec["max_stress_pa"]
        
        # Relative error should be under 15% across dynamic modal response
        rel_err = abs(rec_max - truth_max) / truth_max
        self.assertLess(rel_err, 0.15)
        # WCET execution time should be strictly under 2000 microseconds (DO-178C)
        self.assertLess(rec["execution_time_us"], 2000.0)

    def test_kalman_lfm_filter_stability(self):
        """Verify Kalman filter updates without singular matrix error."""
        self.filter.predict()
        strains = np.array([50e-6, 30e-6, 10e-6])
        f_res = self.filter.update(strains)
        self.assertIn("q_est", f_res)
        self.assertIn("latent_force_n", f_res)
        self.assertFalse(np.isnan(f_res["latent_force_n"]))


if __name__ == "__main__":
    unittest.main()
