"""Behaviour of the Sampler seam: one call in, one plain Snapshot out."""

import pytest

from dashboard.sampler import Sampler, Snapshot


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_sampler(clock, cpu_values, ram=(3_000, 8_000)):
    values = iter(cpu_values)
    return Sampler(
        clock=clock,
        read_cpu=lambda: next(values),
        read_memory=lambda: ram,
    )


def test_snapshot_reports_cpu_and_ram():
    sampler = Sampler(
        clock=FakeClock(),
        read_cpu=lambda: 42.5,
        read_memory=lambda: (3_000, 8_000),
    )

    snap = sampler.snapshot()

    assert isinstance(snap, Snapshot)
    assert snap.cpu_percent == 42.5
    assert snap.ram_used == 3_000
    assert snap.ram_total == 8_000


def test_history_records_one_sample_per_elapsed_second_oldest_first():
    clock = FakeClock()
    sampler = make_sampler(clock, [10.0, 20.0, 30.0])

    assert sampler.snapshot().cpu_history == (10.0,)
    clock.advance(1.0)
    assert sampler.snapshot().cpu_history == (10.0, 20.0)
    clock.advance(1.0)

    snap = sampler.snapshot()

    assert snap.cpu_history == (10.0, 20.0, 30.0)
    assert snap.cpu_percent == 30.0


def test_repeated_calls_within_a_second_reuse_the_last_sample():
    clock = FakeClock()
    sampler = make_sampler(clock, [10.0, 20.0])

    sampler.snapshot()
    clock.advance(0.4)
    snap = sampler.snapshot()

    assert snap.cpu_history == (10.0,)
    assert snap.cpu_percent == 10.0


def test_history_keeps_only_the_last_five_minutes():
    clock = FakeClock()
    values = [float(i % 101) for i in range(350)]
    sampler = make_sampler(clock, values)

    for _ in range(350):
        snap = sampler.snapshot()
        clock.advance(1.0)

    assert len(snap.cpu_history) == 300
    assert snap.cpu_history == tuple(values[50:])
    assert snap.cpu_history[-1] == 46.0


def test_cpu_percent_is_kept_within_zero_and_hundred():
    assert Sampler(clock=FakeClock(), read_cpu=lambda: 130.0,
                   read_memory=lambda: (1, 2)).snapshot().cpu_percent == 100.0
    assert Sampler(clock=FakeClock(), read_cpu=lambda: -3.0,
                   read_memory=lambda: (1, 2)).snapshot().cpu_percent == 0.0


def test_real_system_snapshot_is_plausible():
    snap = Sampler().snapshot()

    assert 0.0 <= snap.cpu_percent <= 100.0
    assert 0 < snap.ram_used <= snap.ram_total
    assert 1 <= len(snap.cpu_history) <= 300
