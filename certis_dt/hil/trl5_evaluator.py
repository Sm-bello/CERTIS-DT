"""
TRL 5 Hardware-In-The-Loop Simulation and Degradation Curve Evaluator.

Executes closed-loop multi-agent swarm missions coupling structural surrogates,
lossy network communications, and automated airworthiness assurance synthesis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np

from certis_dt.sct.geometry import BoomArmGeometry
from certis_dt.sct.truth_fem import StructuralTruthFEM
from certis_dt.sct.surrogate import StructuralSurrogate
from certis_dt.sct.kalman_lfm import KalmanLatentForceFilter
from certis_dt.sct.uncertainty import UncertaintyQuantifier, UncertaintyEstimate
from certis_dt.sct.margin import StructuralMarginEvaluator, MarginEstimate
from certis_dt.sst.agent import UAVPhysicalAgent, UAVState, AgentRole
from certis_dt.sst.virtual_twin import UAVVirtualTwin
from certis_dt.sst.network_channel import TacticalNetworkChannel
from certis_dt.sst.hotl_supervisor import HOTLSupervisor
from certis_dt.sst.swarm_planner import StructuralAwareSwarmPlanner
from certis_dt.sst.metrics import SynchronizationMetricsCalculator, SwarmSynchronizationReport
from certis_dt.aeg.evidence_collector import EvidenceCollector
from certis_dt.aeg.explainability import ExplainabilityEngine
from certis_dt.aeg.docket_exporter import CertificationDocketExporter
from certis_dt.aeg.gsn import GSNAssuranceCase
from certis_dt.hil.fault_injector import FaultInjector, FaultProfile, FaultMode


@dataclass
class MissionSimulationResult:
    duration_s: float
    total_steps: int
    agent_ids: List[str]
    structural_margins: Dict[str, MarginEstimate]
    sync_reports: Dict[str, SwarmSynchronizationReport]
    assurance_case: GSNAssuranceCase
    explainability_records: List[Any]
    execution_times_us: List[float]
    time_series_data: Dict[str, List[float]]


class TRL5MissionHarness:
    """
    Complete end-to-end simulation runner for TRL 5 validation campaigns.
    """

    def __init__(
        self,
        agent_ids: Optional[List[str]] = None,
        dt_seconds: float = 0.01,  # 100 Hz simulation rate
        network_channel: Optional[TacticalNetworkChannel] = None,
        fault_injector: Optional[FaultInjector] = None,
    ):
        self.dt = dt_seconds
        self.agent_ids = agent_ids or ["UAV-LEAD", "UAV-WING-1", "UAV-WING-2"]
        self.channel = network_channel or TacticalNetworkChannel()
        self.fault_injector = fault_injector or FaultInjector()
        
        # Instantiate Layer 1 SCT components for monitored agents
        self.geo = BoomArmGeometry()
        self.sct_truth: Dict[str, StructuralTruthFEM] = {}
        self.sct_surrogate = StructuralSurrogate(geometry=self.geo)
        self.sct_filter: Dict[str, KalmanLatentForceFilter] = {}
        self.sct_uq = UncertaintyQuantifier(geometry=self.geo)
        self.sct_evaluator: Dict[str, StructuralMarginEvaluator] = {}
        
        # Instantiate Layer 2 SST components
        self.physical_agents: Dict[str, UAVPhysicalAgent] = {}
        self.virtual_twins: Dict[str, UAVVirtualTwin] = {}
        self.hotl = HOTLSupervisor()
        self.planner = StructuralAwareSwarmPlanner(hotl_supervisor=self.hotl)
        self.sync_calc = SynchronizationMetricsCalculator()
        
        # Instantiate Layer 3 AEG components
        self.evidence_collector = EvidenceCollector()
        self.explainability = ExplainabilityEngine()
        
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize physical and virtual twin states."""
        self.planner.initialize_v_formation(self.agent_ids)
        
        for aid in self.agent_ids:
            slot = self.planner.slots[aid]
            init_pos = np.array([0.0, 0.0, -50.0]) + slot.relative_offset_ned
            
            self.physical_agents[aid] = UAVPhysicalAgent(agent_id=aid, initial_position=init_pos, role=slot.role)
            self.virtual_twins[aid] = UAVVirtualTwin(agent_id=aid, initial_position=init_pos, role=slot.role)
            
            # SCT per agent
            self.sct_truth[aid] = StructuralTruthFEM(geometry=self.geo)
            self.sct_filter[aid] = KalmanLatentForceFilter(geometry=self.geo, dt=self.dt)
            self.sct_evaluator[aid] = StructuralMarginEvaluator(geometry=self.geo)
            
        # Warm up surrogate to eliminate OS/JIT cold-start timing artifacts
        dummy_strains = np.zeros(len(self.geo.sensor_stations))
        for _ in range(10):
            self.sct_surrogate.reconstruct(dummy_strains)

    def run_mission(
        self,
        duration_s: float = 10.0,
        centroid_velocity_mps: Optional[np.ndarray] = None,
    ) -> MissionSimulationResult:
        """
        Execute full mission flight loop with real-time digital twin synchronization.
        """
        v_target = centroid_velocity_mps if centroid_velocity_mps is not None else np.array([16.0, 0.0, 0.0])
        centroid_pos = np.array([0.0, 0.0, -50.0])
        
        steps = int(duration_s / self.dt)
        current_time = 0.0
        
        # Telemetry & timing tracking
        execution_times_us = []
        latest_margins: Dict[str, MarginEstimate] = {}
        station_ids = [s.station_id for s in self.geo.sensor_stations]
        
        # Time-series logs
        ts_log: Dict[str, List[float]] = {
            "time_s": [],
            "lead_ms": [],
            "lead_stress_mpa": [],
            "lead_credibility": [],
            "swarm_sync_rmse_m": [],
            "channel_latency_ms": [],
        }

        for step_idx in range(steps):
            current_time = step_idx * self.dt
            centroid_pos += v_target * self.dt
            
            # 1. Swarm Planner: calculate commanded velocities
            cmd_velocities = self.planner.plan_swarm_step(
                virtual_twins=self.virtual_twins,
                centroid_target_pos=centroid_pos,
                centroid_target_vel=v_target,
                current_time_s=current_time,
            )
            
            # 2. Advance Physical Agents & SCT Dynamics
            for aid in self.agent_ids:
                agent = self.physical_agents[aid]
                cmd_v = cmd_velocities.get(aid, np.zeros(3))
                
                # Aerodynamic wind & gust injection
                base_gust = np.random.normal(0.0, 0.5, size=3)
                tot_gust, tip_spike_n = self.fault_injector.get_aerodynamic_disturbance(aid, current_time, base_gust)
                
                # Step physical agent kinematics
                p_state = agent.step(self.dt, commanded_velocity=cmd_v, wind_gust=tot_gust)
                
                # Step SCT Truth Model (tip force = steady thrust + aero spike + turbulence)
                steady_thrust_n = 45.0  # Cruise thrust
                truth_res = self.sct_truth[aid].step(self.dt, tip_force_n=steady_thrust_n + tip_spike_n)
                
                # Simulate sparse strain measurements + fault injection
                raw_strains = self.sct_truth[aid].measure_strains(noise_std_microstrain=6.0)
                measured_strains = self.fault_injector.apply_sensor_faults(aid, current_time, station_ids, raw_strains)
                
                # Step SCT Surrogate & Kalman Latent Force Filter
                rec = self.sct_surrogate.reconstruct(measured_strains)
                execution_times_us.append(rec["execution_time_us"])
                
                self.sct_filter[aid].predict()
                f_res = self.sct_filter[aid].update(measured_strains)
                
                # Step SCT Uncertainty Quantification & Margin Evaluation
                u_est = self.sct_uq.evaluate_uncertainty(
                    stress_mean_pa=rec["stress_pa"],
                    modal_covariance=f_res["modal_cov"],
                    innovation_residual=f_res["innovation"],
                    innovation_covariance=f_res["innovation_cov"],
                )
                m_est = self.sct_evaluator[aid].evaluate_margin(u_est, dt_seconds=self.dt)
                latest_margins[aid] = m_est
                
                # Check for explainability trigger on refusal
                if u_est.refusal_to_certify and not agent.refusal_to_certify:
                    self.explainability.generate_refusal_attribution(
                        agent_id=aid,
                        current_time_s=current_time,
                        mahalanobis_d2=u_est.mahalanobis_d2,
                        chi2_threshold=self.sct_uq.chi2_threshold,
                        credibility=u_est.epistemic_credibility,
                        innovation_residual=f_res["innovation"],
                        sensor_station_ids=station_ids,
                    )
                    
                # Update physical agent health state
                agent.update_structural_state(
                    margin_of_safety=m_est.critical_margin_of_safety,
                    peak_stress_pa=rec["max_stress_pa"],
                    epistemic_credibility=u_est.epistemic_credibility,
                    refusal_to_certify=u_est.refusal_to_certify,
                    cumulative_damage=m_est.cumulative_fatigue_damage,
                )
                
                # 3. Transmit telemetry via lossy tactical network
                payload = {
                    "position": p_state.position,
                    "velocity": p_state.velocity,
                    "acceleration": p_state.acceleration,
                    "attitude_rad": p_state.attitude_rad,
                    "margin_of_safety": m_est.critical_margin_of_safety,
                    "peak_stress_pa": rec["max_stress_pa"],
                    "epistemic_credibility": u_est.epistemic_credibility,
                    "refusal_to_certify": u_est.refusal_to_certify,
                    "cumulative_damage": m_est.cumulative_fatigue_damage,
                    "role": agent.role,
                }
                self.channel.transmit_uplink(aid, payload, current_time)

            # 4. Receive Uplink Telemetry in Virtual Twin
            delivered_packets = self.channel.receive_uplink(current_time)
            delivered_by_agent: Dict[str, UAVState] = {}
            for pkt in delivered_packets:
                p_aid = pkt.source_id
                pyld = pkt.payload
                delivered_by_agent[p_aid] = UAVState(
                    agent_id=p_aid,
                    timestamp_s=pkt.sent_timestamp_s,
                    position=pyld["position"],
                    velocity=pyld["velocity"],
                    attitude_rad=pyld["attitude_rad"],
                    angular_velocity=np.zeros(3),
                    acceleration=pyld["acceleration"],
                    margin_of_safety=pyld["margin_of_safety"],
                    peak_stress_pa=pyld["peak_stress_pa"],
                    epistemic_credibility=pyld["epistemic_credibility"],
                    refusal_to_certify=pyld["refusal_to_certify"],
                    cumulative_damage=pyld["cumulative_damage"],
                    battery_charge_pct=100.0,
                    role=pyld["role"],
                )

            # 5. Update Virtual Twin Shadow & Predict Forward
            step_divs = []
            for aid in self.agent_ids:
                twin = self.virtual_twins[aid]
                if aid in delivered_by_agent:
                    twin.ingest_telemetry(delivered_by_agent[aid], current_time)
                else:
                    twin.predict_forward(self.dt, current_time)
                    
                # Compute synchronization divergence against true physical position
                div = twin.compute_divergence(self.physical_agents[aid].get_state(), current_time)
                step_divs.append(div.position_error_m)

            # 6. HOTL Supervisor Timeout Processing
            self.hotl.process_pending_requests(current_time)
            
            # Periodic logging
            if step_idx % 10 == 0:
                lead_id = self.agent_ids[0]
                ts_log["time_s"].append(current_time)
                ts_log["lead_ms"].append(latest_margins[lead_id].critical_margin_of_safety)
                ts_log["lead_stress_mpa"].append(self.physical_agents[lead_id].peak_stress_pa / 1.0e6)
                ts_log["lead_credibility"].append(self.physical_agents[lead_id].epistemic_credibility)
                ts_log["swarm_sync_rmse_m"].append(float(np.mean(step_divs)))
                ts_log["channel_latency_ms"].append(self.channel.get_channel_metrics()["mean_latency_ms"])

        # Compute synchronization reports for all agents
        sync_reports = {}
        for aid in self.agent_ids:
            sync_reports[aid] = self.sync_calc.compute_agent_metrics(
                agent_id=aid,
                divergence_history=self.virtual_twins[aid].divergence_history,
            )

        # Synthesize GSN Assurance Case
        assurance_case = self.evidence_collector.build_assurance_case(
            structural_margins=latest_margins,
            sync_reports=sync_reports,
            execution_times_us=execution_times_us,
            has_causal_explanations=True,
        )

        return MissionSimulationResult(
            duration_s=duration_s,
            total_steps=steps,
            agent_ids=self.agent_ids,
            structural_margins=latest_margins,
            sync_reports=sync_reports,
            assurance_case=assurance_case,
            explainability_records=self.explainability.records,
            execution_times_us=execution_times_us,
            time_series_data=ts_log,
        )
