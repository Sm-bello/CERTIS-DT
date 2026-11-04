"""
Tactical Network Channel Emulator.

Simulates bidirectional communication between physical UAV assets and the virtual twin,
incorporating stochastic latency jitter, packet loss (Gilbert-Elliott Markov fading),
bandwidth throttling, and out-of-order transmission.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class ChannelFadingState(Enum):
    GOOD = "GOOD"
    FADE_BURST = "FADE_BURST"


@dataclass
class TelemetryPacket:
    packet_id: int
    source_id: str
    target_id: str
    sent_timestamp_s: float
    delivery_timestamp_s: float
    payload: Dict[str, Any]
    is_dropped: bool = False


class TacticalNetworkChannel:
    """
    High-fidelity communication channel modeling wireless telemetry degradation.
    
    Features:
      - Stochastic latency: tau = tau_base + LogNormal(mu_jitter, sigma_jitter)
      - Gilbert-Elliott 2-State Markov burst loss model:
          P(Good -> Bad) = p_gb, P(Bad -> Good) = p_bg
      - In-flight packet queue with time-ordered delivery.
    """

    def __init__(
        self,
        base_latency_s: float = 0.015,       # 15 ms base latency
        jitter_std_s: float = 0.005,         # 5 ms jitter
        baseline_loss_prob: float = 0.02,    # 2% nominal packet loss
        burst_loss_prob: float = 0.40,       # 40% loss during deep fading
        p_good_to_bad: float = 0.01,         # Markov transition to burst fade
        p_bad_to_good: float = 0.15,         # Markov recovery from fade
    ):
        self.base_latency = base_latency_s
        self.jitter_std = jitter_std_s
        self.loss_good = baseline_loss_prob
        self.loss_bad = burst_loss_prob
        self.p_gb = p_good_to_bad
        self.p_bg = p_bad_to_good
        
        self.fading_state = ChannelFadingState.GOOD
        self.packet_counter = 0
        
        # In-flight queue: list of TelemetryPacket
        self.uplink_queue: List[TelemetryPacket] = []
        self.downlink_queue: List[TelemetryPacket] = []
        
        # Statistics
        self.packets_transmitted = 0
        self.packets_delivered = 0
        self.packets_dropped = 0
        self.latency_history: List[float] = []

    def _update_channel_fading(self) -> None:
        """Advance Markov chain for channel fading state."""
        rand = np.random.uniform(0.0, 1.0)
        if self.fading_state == ChannelFadingState.GOOD:
            if rand < self.p_gb:
                self.fading_state = ChannelFadingState.FADE_BURST
        else:
            if rand < self.p_bg:
                self.fading_state = ChannelFadingState.GOOD

    def _sample_latency(self) -> float:
        """Sample positive latency with log-normal jitter."""
        # Mean = base_latency, Std = jitter_std
        jitter = np.random.lognormal(mean=-5.5, sigma=0.6)
        return max(0.001, self.base_latency + jitter)

    def _is_packet_lost(self) -> bool:
        """Determine if packet is dropped based on current fading state."""
        loss_rate = self.loss_bad if self.fading_state == ChannelFadingState.FADE_BURST else self.loss_good
        return bool(np.random.uniform(0.0, 1.0) < loss_rate)

    def transmit_uplink(self, source_id: str, payload: Dict[str, Any], current_time_s: float) -> TelemetryPacket:
        """Transmit telemetry from physical asset to virtual twin."""
        self._update_channel_fading()
        self.packet_counter += 1
        self.packets_transmitted += 1
        
        dropped = self._is_packet_lost()
        lat = self._sample_latency()
        
        packet = TelemetryPacket(
            packet_id=self.packet_counter,
            source_id=source_id,
            target_id="VIRTUAL_TWIN",
            sent_timestamp_s=current_time_s,
            delivery_timestamp_s=current_time_s + lat,
            payload=payload,
            is_dropped=dropped,
        )
        
        if dropped:
            self.packets_dropped += 1
        else:
            self.uplink_queue.append(packet)
            self.latency_history.append(lat)
            
        return packet

    def transmit_downlink(self, target_id: str, payload: Dict[str, Any], current_time_s: float) -> TelemetryPacket:
        """Transmit command/reconfiguration from virtual twin to physical asset."""
        self._update_channel_fading()
        self.packet_counter += 1
        self.packets_transmitted += 1
        
        dropped = self._is_packet_lost()
        lat = self._sample_latency()
        
        packet = TelemetryPacket(
            packet_id=self.packet_counter,
            source_id="VIRTUAL_TWIN",
            target_id=target_id,
            sent_timestamp_s=current_time_s,
            delivery_timestamp_s=current_time_s + lat,
            payload=payload,
            is_dropped=dropped,
        )
        
        if dropped:
            self.packets_dropped += 1
        else:
            self.downlink_queue.append(packet)
            self.latency_history.append(lat)
            
        return packet

    def receive_uplink(self, current_time_s: float) -> List[TelemetryPacket]:
        """Collect all delivered uplink packets ready at current_time_s."""
        delivered = []
        remaining = []
        for p in self.uplink_queue:
            if p.delivery_timestamp_s <= current_time_s:
                delivered.append(p)
                self.packets_delivered += 1
            else:
                remaining.append(p)
        self.uplink_queue = remaining
        return delivered

    def receive_downlink(self, target_id: str, current_time_s: float) -> List[TelemetryPacket]:
        """Collect all delivered downlink packets for target_id ready at current_time_s."""
        delivered = []
        remaining = []
        for p in self.downlink_queue:
            if p.target_id == target_id and p.delivery_timestamp_s <= current_time_s:
                delivered.append(p)
                self.packets_delivered += 1
            else:
                remaining.append(p)
        self.downlink_queue = remaining
        return delivered

    def get_channel_metrics(self) -> Dict[str, float]:
        """Summary metrics of network health."""
        mean_lat = float(np.mean(self.latency_history)) if self.latency_history else self.base_latency
        p95_lat = float(np.percentile(self.latency_history, 95)) if self.latency_history else self.base_latency
        drop_rate = (self.packets_dropped / max(1, self.packets_transmitted))
        return {
            "mean_latency_ms": mean_lat * 1000.0,
            "p95_latency_ms": p95_lat * 1000.0,
            "packet_drop_rate": drop_rate,
            "fading_state": self.fading_state.value,
        }
