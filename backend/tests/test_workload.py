"""Unit tests for workload generation, traffic patterns, and reproducibility."""

import pytest
from backend.simulator.schemas import WorkloadConfig, WorkloadPattern
from backend.simulator.workload import WorkloadGenerator


def test_constant_traffic_pattern():
    """Verify constant pattern generates consistent arrival rate across time."""
    cfg = WorkloadConfig(
        requests_per_second=200.0,
        pattern=WorkloadPattern.CONSTANT,
        duration_seconds=10.0,
        seed=42,
    )
    gen = WorkloadGenerator(cfg)
    assert gen.get_rate_at(0.0) == 200.0
    assert gen.get_rate_at(5.0) == 200.0
    assert gen.get_rate_at(10.0) == 200.0

    steps = gen.generate_steps()
    assert len(steps) == 10
    for s in steps:
        assert s.offered_rps == 200.0
        assert s.request_count == 200


def test_ramp_up_traffic_pattern():
    """Verify ramp-up pattern increases rate monotonically over duration."""
    cfg = WorkloadConfig(
        requests_per_second=500.0,
        pattern=WorkloadPattern.RAMP_UP,
        duration_seconds=20.0,
        seed=42,
    )
    gen = WorkloadGenerator(cfg)
    rate_start = gen.get_rate_at(0.0)
    rate_mid = gen.get_rate_at(10.0)
    rate_end = gen.get_rate_at(20.0)

    assert rate_start < rate_mid < rate_end
    assert rate_start == pytest.approx(100.0, rel=0.01)  # 20% of 500
    assert rate_end == pytest.approx(500.0, rel=0.01)


def test_burst_traffic_pattern():
    """Verify burst pattern elevates rate strictly within the burst window."""
    cfg = WorkloadConfig(
        requests_per_second=300.0,
        pattern=WorkloadPattern.BURST,
        burst_multiplier=3.0,
        burst_start_sec=10.0,
        burst_duration_sec=5.0,
        duration_seconds=20.0,
        seed=42,
    )
    gen = WorkloadGenerator(cfg)
    assert gen.get_rate_at(5.0) == 300.0
    assert gen.get_rate_at(10.0) == 900.0  # 300 * 3.0
    assert gen.get_rate_at(14.9) == 900.0
    assert gen.get_rate_at(15.1) == 300.0


def test_spike_traffic_pattern():
    """Verify spike pattern generates sudden concentrated surge."""
    cfg = WorkloadConfig(
        requests_per_second=200.0,
        pattern=WorkloadPattern.SPIKE,
        burst_multiplier=4.0,
        burst_start_sec=5.0,
        burst_duration_sec=2.0,
        duration_seconds=10.0,
        seed=42,
    )
    gen = WorkloadGenerator(cfg)
    assert gen.get_rate_at(2.0) == 200.0
    assert gen.get_rate_at(5.5) == 800.0  # 200 * 4.0
    assert gen.get_rate_at(8.0) == 200.0


def test_workload_reproducibility_with_seed():
    """Identical seeds must produce identical request streams."""
    cfg1 = WorkloadConfig(
        requests_per_second=100.0,
        duration_seconds=5.0,
        read_ratio=0.7,
        seed=12345,
    )
    cfg2 = WorkloadConfig(
        requests_per_second=100.0,
        duration_seconds=5.0,
        read_ratio=0.7,
        seed=12345,
    )
    requests1 = WorkloadGenerator(cfg1).generate_requests()
    requests2 = WorkloadGenerator(cfg2).generate_requests()

    assert len(requests1) == len(requests2)
    for r1, r2 in zip(requests1, requests2):
        assert r1.request_id == r2.request_id
        assert r1.arrival_time == pytest.approx(r2.arrival_time, abs=1e-9)
        assert r1.is_read == r2.is_read


def test_workload_different_seeds_diverge():
    """Different seeds must produce different stochastic arrival distributions."""
    cfg1 = WorkloadConfig(requests_per_second=100.0, duration_seconds=5.0, seed=111)
    cfg2 = WorkloadConfig(requests_per_second=100.0, duration_seconds=5.0, seed=999)

    reqs1 = WorkloadGenerator(cfg1).generate_requests()
    reqs2 = WorkloadGenerator(cfg2).generate_requests()

    arrival_times1 = [r.arrival_time for r in reqs1]
    arrival_times2 = [r.arrival_time for r in reqs2]
    assert arrival_times1 != arrival_times2


def test_read_write_ratio_bounds():
    """Verify read/write ratio partitions requests correctly."""
    # 100% reads
    cfg_all_reads = WorkloadConfig(requests_per_second=50.0, read_ratio=1.0, duration_seconds=5.0, seed=42)
    reqs_read = WorkloadGenerator(cfg_all_reads).generate_requests()
    assert all(r.is_read for r in reqs_read)

    # 100% writes
    cfg_all_writes = WorkloadConfig(requests_per_second=50.0, read_ratio=0.0, duration_seconds=5.0, seed=42)
    reqs_write = WorkloadGenerator(cfg_all_writes).generate_requests()
    assert all(not r.is_read for r in reqs_write)

    # 75% reads stochastic check
    cfg_mixed = WorkloadConfig(requests_per_second=200.0, read_ratio=0.75, duration_seconds=10.0, seed=42)
    reqs_mixed = WorkloadGenerator(cfg_mixed).generate_requests()
    actual_read_ratio = sum(1 for r in reqs_mixed if r.is_read) / len(reqs_mixed)
    assert actual_read_ratio == pytest.approx(0.75, abs=0.05)
