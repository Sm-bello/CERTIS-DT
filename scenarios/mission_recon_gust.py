"""
Scenario 1: Tactical Reconnaissance Under Turbulent Gust Spectra.

Simulates a 3-UAV formation executing a tactical reconnaissance mission through
turbulent atmospheric gusts, demonstrating real-time surrogate stress estimation
and sub-2cm virtual twin trajectory synchronization.
"""

from pathlib import Path
from certis_dt.hil.trl5_evaluator import TRL5MissionHarness
from certis_dt.aeg.docket_exporter import CertificationDocketExporter


def run_scenario() -> None:
    print("=" * 75)
    print(" SCENARIO 1: Tactical Reconnaissance Under Turbulent Gust Spectra")
    print("=" * 75)
    
    harness = TRL5MissionHarness(
        agent_ids=["UAV-ALPHA", "UAV-BRAVO", "UAV-CHARLIE"],
        dt_seconds=0.01,
    )
    
    print("[*] Executing 10-second mission flight loop (1,000 epochs at 100 Hz)...")
    res = harness.run_mission(duration_s=10.0)
    
    print("\n[+] Flight Loop Completed.")
    print(f"    - Reconstructed Stress WCET : {min(res.execution_times_us):.1f} us min / {max(res.execution_times_us):.1f} us max")
    print(f"    - Lead Agent Margin of Safety: {res.structural_margins['UAV-ALPHA'].critical_margin_of_safety:+.3f}")
    print(f"    - Swarm Position RMSE (m)   : {res.sync_reports['UAV-ALPHA'].mean_position_rmse_m:.3f} m")
    print(f"    - Airworthiness Verdict     : [{res.assurance_case.evaluate_tree().value}]")
    
    out_dir = Path("./output/scenario_recon_gust")
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
