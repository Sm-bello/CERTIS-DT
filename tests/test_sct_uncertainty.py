"""
Unit tests for Layer 1 SCT: Uncertainty Quantification and Margin Evaluation.
"""

import unittest
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.truth_fem import StructuralTruthFEM
from certis_dt.sct.uncertainty import UncertaintyQuantifier
from certis_dt.sct.margin import StructuralMarginEvaluator


class TestUncertaintyAndMargin(unittest.TestCase):
    def setUp(self):
        self.geo = BoomArmGeometry()
        self.truth = StructuralTruthFEM(geometry=self.geo, num_modes=3)
        self.uq = UncertaintyQuantifier(geometry=self.geo, truth_fem=self.truth)
        self.evaluator = StructuralMarginEvaluator(geometry=self.geo)

    def test_nominal_uncertainty_evaluation(self):
        """Verify nominal uncertainty evaluation passes without refusal."""
        stress_mean = np.full(len(self.truth.x_grid), 50.0e6)
        modal_cov = np.eye(3) * 1e-8
        r = np.array([2e-6, -1e-6, 1e-6])
        S = np.eye(3) * 1e-10
        
        u_est = self.uq.evaluate_uncertainty(stress_mean, modal_cov, r, S)
        self.assertFalse(u_est.refusal_to_certify)
        self.assertGreater(u_est.epistemic_credibility, 0.70)
        
        m_est = self.evaluator.evaluate_margin(u_est, dt_seconds=0.01)
        self.assertTrue(m_est.is_airworthy)
        self.assertEqual(m_est.certification_status, "COMPLIANT")

    def test_epistemic_refusal_on_severe_anomaly(self):
        """Verify epistemic refusal triggers when innovation residual explodes."""
        stress_mean = np.full(len(self.truth.x_grid), 50.0e6)
        modal_cov = np.eye(3) * 1e-8
        # High residual (e.g. gauge debonding or loose wiring)
        r = np.array([500e-6, -400e-6, 350e-6])
        S = np.eye(3) * 1e-10
        
        u_est = self.uq.evaluate_uncertainty(stress_mean, modal_cov, r, S)
        self.assertTrue(u_est.refusal_to_certify)
        self.assertLess(u_est.epistemic_credibility, 0.25)
        
        m_est = self.evaluator.evaluate_margin(u_est, dt_seconds=0.01)
        self.assertFalse(m_est.is_airworthy)
        self.assertEqual(m_est.certification_status, "DISQUALIFIED_OOD")


if __name__ == "__main__":
    unittest.main()
