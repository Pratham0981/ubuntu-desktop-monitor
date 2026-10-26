"""The entry point only needs to understand its one flag."""

from dashboard.app import wants_on_top


def test_on_top_flag_is_recognised():
    assert wants_on_top(["dashboard-widget", "--on-top"]) is True


def test_normal_launch_does_not_ask_for_on_top():
    assert wants_on_top(["dashboard-widget"]) is False
