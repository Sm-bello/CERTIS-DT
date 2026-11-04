"""
Scenario 2: Sparse Sensor Dropout & Epistemic Refusal-to-Certify.

Injects physical strain gauge detachment/drift at t=3.0s, demonstrating
Mahalanobis innovation gating, epistemic credibility collapse, explainability-by-construction,
and safe autonomous flight envelope freezing (EASA AI Level 2).
"""

from pathlib import Path
from certis_dt.hil.trl5_evaluator import TRL5MissionHarness
from certis_dt.hil.fault_injector import FaultInjector, FaultProfile, FaultMode
from certis_dt.aeg.docket_exporter import CertificationDocketExporter


def run_scenario() -> None:
    print("=" * 75)
    print(" SCENARIO 2: Sparse Sensor Dropout & Epistemic Refusal-to-Certify")
    print("=" * 75)
    
    injector = FaultInjector([
        FaultProfile(
            fault_mode=FaultMode.SENSOR_BIAS_DRIFT,
            start_time_s=3.0,
            end_time_s=8.0,
            target_agent_id="UAV-ALPHA",
            target_sensor_id="SG-02",
            magnitude=350.0,
        )
    ])
    
    harness = TRL5MissionHarness(
        agent_ids=["UAV-ALPHA", "UAV-BRAVO", "UAV-CHARLIE"],
        dt_seconds=0.01,
        fault_injector=injector,
    )
    
    print("[*] Executing mission with sensor drift fault injected at t=3.0s...")
    res = harness.run_mission(duration_s=8.0)
    
    print("\n[+] Mission Completed.")
    print("--- Explainability-by-Construction Audit Trail ---")
    for rec in res.explainability_records:
        print(f"  [{rec.record_id}] Event: {rec.event_category} (Agent: {rec.target_agent_id} at {rec.timestamp_s:.2f}s)")
        print(f"       Hypothesis : {rec.physical_mechanism_hypothesis}")
        print(f"       Action     : {rec.safety_mitigation_action}")
        print(f"       Verdict    : {rec.auditor_verdict}")
        
    print(f"\n[+] Overall Assurance Verdict: [{res.assurance_case.evaluate_tree().value}]")
    
    out_dir = Path("./output/scenario_sensor_dropout")
    CertificationDocketExporter.export_markdown_report(
        assurance_case=res.assurance_case,
        structural_margins=res.structural_margins,
        sync_reports=res.sync_reports,
        explainability_records=res.explainability_records,
        output_path=out_dir / "CERTIFICATION_REPORT.md",
    )
    print(f"[+] Output generated at {out_dir / 'CERTIFICATION_REPORT.md'}")


if __name__ == "__main__":
    run_scenario()
