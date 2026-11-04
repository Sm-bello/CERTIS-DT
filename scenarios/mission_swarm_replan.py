"""
Scenario 3: Structural-Aware Swarm Autonomy (SASA) Re-Planning.

Simulates extreme dynamic loads and fatigue on formation lead UAV, triggering
autonomous role swapping (promoting healthiest wingman to leader) and cruise
speed derating to preserve swarm structural integrity under airworthiness standards.
"""

from pathlib import Path
from certis_dt.hil.trl5_evaluator import TRL5MissionHarness
from certis_dt.hil.fault_injector import FaultInjector, FaultProfile, FaultMode
from certis_dt.aeg.docket_exporter import CertificationDocketExporter


def run_scenario() -> None:
    print("=" * 75)
    print(" SCENARIO 3: Structural-Aware Swarm Autonomy (SASA) Re-Planning")
    print("=" * 75)
    
    # Inject heavy aerodynamic shock load on the leader at t=2.0s
    injector = FaultInjector([
        FaultProfile(
            fault_mode=FaultMode.EXTREME_MICROBURST_GUST,
            start_time_s=2.0,
            end_time_s=5.0,
            target_agent_id="UAV-LEAD",
            magnitude=2.2,
        )
    ])
    
    harness = TRL5MissionHarness(
        agent_ids=["UAV-LEAD", "UAV-WINGMAN-A", "UAV-WINGMAN-B"],
        dt_seconds=0.01,
        fault_injector=injector,
    )
    
    print("[*] Executing mission with severe microburst gust on leader...")
    res = harness.run_mission(duration_s=8.0)
    
    print("\n[+] Mission Completed.")
    print("--- Swarm Autonomy Re-Planning Events ---")
    for event in harness.planner.replan_event_log:
        print(f"  [{event['time']}] {event['event']}")
        
    print(f"\n[+] Cruise Velocity Derate: {harness.planner.nominal_speed:.1f} m/s -> {harness.planner.current_max_speed:.1f} m/s")
    print(f"[+] Final Airworthiness Verdict: [{res.assurance_case.evaluate_tree().value}]")
    
    out_dir = Path("./output/scenario_swarm_replan")
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
