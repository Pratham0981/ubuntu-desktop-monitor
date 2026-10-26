"""CPU temperature, including machines that expose no sensor at all."""

from dashboard.thermal import read_cpu_temp


def write_zone(root, index, name, millidegrees):
    zone = root / f"thermal_zone{index}"
    zone.mkdir()
    (zone / "type").write_text(name)
    (zone / "temp").write_text(str(millidegrees))


def test_prefers_the_cpu_package_sensor(tmp_path):
    write_zone(tmp_path, 0, "acpitz", 54_000)
    write_zone(tmp_path, 1, "x86_pkg_temp", 53_000)
    write_zone(tmp_path, 2, "iwlwifi_1", 43_000)

    assert read_cpu_temp(tmp_path, sensors=lambda: {}) == 53.0


def test_falls_back_to_acpitz(tmp_path):
    write_zone(tmp_path, 0, "acpitz", 54_500)

    assert read_cpu_temp(tmp_path, sensors=lambda: {}) == 54.5


def test_missing_sensor_returns_none(tmp_path):
    assert read_cpu_temp(tmp_path, sensors=lambda: {}) is None


def test_unreadable_zone_is_skipped(tmp_path):
    broken = tmp_path / "thermal_zone0"
    broken.mkdir()
    (broken / "type").write_text("x86_pkg_temp")
    # no temp file at all
    write_zone(tmp_path, 1, "acpitz", 48_000)

    assert read_cpu_temp(tmp_path, sensors=lambda: {}) == 48.0


def test_real_machine_reports_a_plausible_temperature():
    value = read_cpu_temp()

    assert value is None or 10.0 <= value <= 110.0
