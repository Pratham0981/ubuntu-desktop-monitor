"""Settings file, rate formatting and the new sampler readings (no display needed)."""

import pytest

from dashboard.config import load_settings, save_settings
from dashboard.format import format_rate, format_uptime
from dashboard.sampler import Sampler


def test_settings_round_trip(tmp_path):
    path = tmp_path / "dash" / "settings.json"
    save_settings({"position": [10, 20], "opacity": 0.65}, path)
    assert load_settings(path) == {"position": [10, 20], "opacity": 0.65}


def test_missing_or_damaged_settings_mean_no_settings(tmp_path):
    assert load_settings(tmp_path / "none.json") == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert load_settings(broken) == {}
    listy = tmp_path / "list.json"
    listy.write_text("[1, 2]")
    assert load_settings(listy) == {}


@pytest.mark.parametrize(
    "value, text",
    [(0, "0 B/s"), (900, "900 B/s"), (1536, "1.5 KB/s"), (5 * 1024**2, "5.0 MB/s"), (-5, "0 B/s")],
)
def test_format_rate(value, text):
    assert format_rate(value) == text


@pytest.mark.parametrize(
    "seconds, text",
    [(30, "0m"), (600, "10m"), (3 * 3600 + 120, "3h 2m"), (3 * 86400 + 4 * 3600, "3d 4h")],
)
def test_format_uptime(seconds, text):
    assert format_uptime(seconds) == text


def make_sampler(net_readings, cores=(10.0, 150.0, -5.0)):
    clock_values = iter(range(0, 1000, 2))
    net = iter(net_readings)
    return Sampler(
        interval=1.0,
        clock=lambda: float(next(clock_values)),
        read_cpu=lambda: 10.0,
        read_memory=lambda: (1, 2),
        read_disk=lambda: None,
        read_temp=lambda: None,
        read_processes=lambda: (),
        read_cores=lambda: cores,
        read_net=lambda: next(net),
        read_system=lambda: ((0.5, 0.4, 0.3), 3600.0),
    )


def test_cores_are_clamped_and_system_readings_pass_through():
    snapshot = make_sampler([(0, 0)]).snapshot()
    assert snapshot.core_percents == (10.0, 100.0, 0.0)
    assert snapshot.load_avg == (0.5, 0.4, 0.3)
    assert snapshot.uptime == 3600.0


def test_network_speed_is_bytes_per_second_between_samples():
    sampler = make_sampler([(1000, 500), (3000, 1500)])
    first = sampler.snapshot()
    assert (first.net_down, first.net_up) == (0.0, 0.0)
    second = sampler.snapshot()  # the fake clock advances 2 s per call
    assert second.net_down == pytest.approx(1000.0)
    assert second.net_up == pytest.approx(500.0)


def test_network_counter_reset_never_reports_negative_speed():
    sampler = make_sampler([(5000, 5000), (100, 100)])
    sampler.snapshot()
    snapshot = sampler.snapshot()
    assert snapshot.net_down == 0.0 and snapshot.net_up == 0.0
