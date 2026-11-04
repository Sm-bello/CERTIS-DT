"""
Unit tests for Layer 3 AEG: Goal Structuring Notation (GSN) and Evidence Generation.
"""

import unittest
import json
import numpy as np

from certis_dt.aeg.gsn import GSNAssuranceCase, GSNNode, GSNNodeType, GSNStatus
from certis_dt.aeg.evidence_collector import EvidenceCollector
from certis_dt.sct.margin import MarginEstimate
from certis_dt.sst.metrics import SwarmSynchronizationReport


class TestAirworthinessEvidenceGenerator(unittest.TestCase):
    def test_gsn_hierarchical_evaluation(self):
        """Verify recursive status propagation in GSN tree."""
        case = GSNAssuranceCase(case_id="TEST-CASE", title="Test GSN Case")
        
        g1 = GSNNode("G1", GSNNodeType.GOAL, "Top level goal")
        case.add_node(g1, is_root=True)
        
        s1 = GSNNode("S1", GSNNodeType.STRATEGY, "Decomposition strategy")
        case.add_node(s1)
        case.add_relationship("G1", "S1")
        
        sol1 = GSNNode("Sol1", GSNNodeType.SOLUTION, "Evidence 1", status=GSNStatus.SATISFIED)
        sol2 = GSNNode("Sol2", GSNNodeType.SOLUTION, "Evidence 2", status=GSNStatus.SATISFIED)
        case.add_node(sol1)
        case.add_node(sol2)
        case.add_relationship("S1", "Sol1")
        case.add_relationship("S1", "Sol2")
        
        # When all children pass, root is SATISFIED
        self.assertEqual(case.evaluate_tree(), GSNStatus.SATISFIED)
        
        # When one solution fails, root transitions to VIOLATED
        sol2.status = GSNStatus.VIOLATED
        self.assertEqual(case.evaluate_tree(), GSNStatus.VIOLATED)
        
        # When one solution is refused, root transitions to DISQUALIFIED_REFUSED
        sol2.status = GSNStatus.DISQUALIFIED_REFUSED
        self.assertEqual(case.evaluate_tree(), GSNStatus.DISQUALIFIED_REFUSED)

    def test_sacm_json_and_mermaid_export(self):
        """Verify SACM JSON serialization and Mermaid string output."""
        case = GSNAssuranceCase(case_id="SACM-TEST")
        g1 = GSNNode("G1", GSNNodeType.GOAL, "System is airworthy", status=GSNStatus.SATISFIED)
        sol1 = GSNNode("Sol1", GSNNodeType.SOLUTION, "Telemetry proof", status=GSNStatus.SATISFIED)
        case.add_node(g1, is_root=True)
        case.add_node(sol1)
        case.add_relationship("G1", "Sol1")
        
        mermaid_str = case.to_mermaid()
        self.assertIn("flowchart TD", mermaid_str)
        self.assertIn("G1[", mermaid_str)
        
        sacm_json = case.to_sacm_json()
        parsed = json.loads(sacm_json)
        self.assertEqual(parsed["sacm_version"], "2.0")
        self.assertEqual(parsed["overall_status"], "SATISFIED")


if __name__ == "__main__":
    unittest.main()
