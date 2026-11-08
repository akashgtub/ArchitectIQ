"""Workload generation engine for ArchitectIQ.

Generates deterministic, reproducible traffic profiles (constant, ramp-up, burst, spike)
with explicit read/write proportions and arrival timestamps.
"""

from __future__ import annotations

import math
from typing import List
import numpy as np

from backend.simulator.schemas import WorkloadConfig, WorkloadPattern


class SimulatedRequest:
    """A simulated request event traversing the system architecture."""

    def __init__(
        self,
        request_id: int,
        arrival_time: float,
        is_read: bool,
    ) -> None:
        self.request_id = request_id
        self.arrival_time = arrival_time
        self.is_read = is_read
        self.completed: bool = False
        self.dropped: bool = False
        self.drop_reason: str = ""
        self.dropped_at_component: str = ""
        self.hop_latencies: dict[str, float] = {}
        self.total_latency_ms: float = 0.0

    def mark_completed(self, total_latency_ms: float) -> None:
        """Mark the request as successfully processed."""
        self.completed = True
        self.total_latency_ms = max(0.0, total_latency_ms)

    def mark_dropped(self, component_id: str, reason: str) -> None:
        """Mark the request as dropped/failed due to component saturation or queue overflow."""
        self.dropped = True
        self.dropped_at_component = component_id
        self.drop_reason = reason


class WorkloadStep:
    """Aggregated traffic metrics for a single discrete simulation time slice."""

    def __init__(
        self,
        timestamp: float,
        duration: float,
        offered_rps: float,
        request_count: int,
        read_count: int,
        write_count: int,
    ) -> None:
        self.timestamp = timestamp
        self.duration = duration
        self.offered_rps = offered_rps
        self.request_count = request_count
        self.read_count = read_count
        self.write_count = write_count


class WorkloadGenerator:
    """Generates reproducible arrival rates and discrete request events from WorkloadConfig."""

    def __init__(self, config: WorkloadConfig) -> None:
        self.config = config
        self._rng = np.random.RandomState(config.seed)

    def get_rate_at(self, t: float) -> float:
        """Calculate the instantaneous arrival rate (RPS) at time t (seconds)."""
        base_rps = self.config.requests_per_second

        if self.config.pattern == WorkloadPattern.CONSTANT:
            return base_rps

        elif self.config.pattern == WorkloadPattern.RAMP_UP:
            # Linear ramp from 20% base RPS up to 100% at end of horizon
            horizon = max(1.0, self.config.duration_seconds)
            progress = min(1.0, max(0.0, t / horizon))
            return base_rps * (0.2 + 0.8 * progress)

        elif self.config.pattern == WorkloadPattern.BURST:
            # Multiplier applied during [burst_start_sec, burst_start_sec + burst_duration_sec]
            burst_start = self.config.burst_start_sec
            burst_end = burst_start + self.config.burst_duration_sec
            if burst_start <= t < burst_end:
                return base_rps * self.config.burst_multiplier
            return base_rps

        elif self.config.pattern == WorkloadPattern.SPIKE:
            # A concentrated surge over a short window
            spike_start = self.config.burst_start_sec
            spike_duration = min(self.config.burst_duration_sec, max(2.0, self.config.step_size_sec * 2))
            spike_end = spike_start + spike_duration
            if spike_start <= t < spike_end:
                return base_rps * self.config.burst_multiplier
            return base_rps

        return base_rps

    def generate_steps(self) -> List[WorkloadStep]:
        """Generate time-step summaries across the simulation duration."""
        steps: List[WorkloadStep] = []
        step_size = self.config.step_size_sec
        duration = self.config.duration_seconds
        num_steps = max(1, int(math.ceil(duration / step_size)))

        for i in range(num_steps):
            t = i * step_size
            current_duration = min(step_size, duration - t)
            rate = self.get_rate_at(t)
            expected_requests = rate * current_duration
            # Deterministic rounding with Poisson variance when rate > 0
            count = int(round(expected_requests))
            read_count = int(round(count * self.config.read_ratio))
            write_count = max(0, count - read_count)

            steps.append(
                WorkloadStep(
                    timestamp=t,
                    duration=current_duration,
                    offered_rps=rate,
                    request_count=count,
                    read_count=read_count,
                    write_count=write_count,
                )
            )

        return steps

    def generate_requests(self, max_requests: int = 50000) -> List[SimulatedRequest]:
        """Generate discrete SimulatedRequest events for detailed event-based simulation.

        Uses Poisson arrival intervals (exponential inter-arrival times) seeded by config.seed.
        Caps generated requests at max_requests to maintain deterministic execution time.
        """
        requests: List[SimulatedRequest] = []
        current_time = 0.0
        duration = self.config.duration_seconds
        req_id = 0

        # Pre-seed RNG for exact determinism
        rng = np.random.RandomState(self.config.seed)

        while current_time < duration and req_id < max_requests:
            rate = self.get_rate_at(current_time)
            if rate <= 0.0:
                # Advance by 1 step if idle
                current_time += self.config.step_size_sec
                continue

            # Exponential inter-arrival time (Poisson process)
            inter_arrival = rng.exponential(1.0 / rate)
            current_time += inter_arrival

            if current_time >= duration:
                break

            # Read vs Write determination
            is_read = rng.random_sample() < self.config.read_ratio

            req = SimulatedRequest(
                request_id=req_id,
                arrival_time=current_time,
                is_read=is_read,
            )
            requests.append(req)
            req_id += 1

        return requests
