"""Formatting helpers shared by every row of the widget."""

from dashboard.format import format_bytes, format_pair, format_percent


def test_bytes_use_binary_units_with_one_decimal():
    assert format_bytes(512) == "512 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(4_294_967_296) == "4.0 GB"
    assert format_bytes(1_099_511_627_776) == "1.0 TB"


def test_pairs_read_used_over_total():
    assert format_pair(4_294_967_296, 8_589_934_592) == "4.0 GB / 8.0 GB"


def test_percent_is_rounded_to_a_whole_number():
    assert format_percent(42.4) == "42%"
    assert format_percent(99.6) == "100%"
