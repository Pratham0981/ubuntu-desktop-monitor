"""Top processes by CPU use."""

import psutil

from dashboard.procs import ProcessInfo, read_top_processes


class FakeProcess:
    def __init__(self, pid, name, cpu, memory):
        self.info = {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_percent": memory,
        }


class VanishedProcess:
    @property
    def info(self):
        raise psutil.NoSuchProcess(999)


def test_processes_are_ranked_by_cpu_and_limited():
    procs = [
        FakeProcess(1, "one", 5.0, 1.0),
        FakeProcess(2, "two", 50.0, 2.0),
        FakeProcess(3, "three", 20.0, 9.0),
    ]

    top = read_top_processes(limit=2, processes=procs)

    assert [p.name for p in top] == ["two", "three"]
    assert top[0] == ProcessInfo(pid=2, name="two", cpu_percent=50.0, memory_percent=2.0)


def test_memory_breaks_cpu_ties():
    procs = [
        FakeProcess(1, "light", 10.0, 1.0),
        FakeProcess(2, "heavy", 10.0, 8.0),
    ]

    assert read_top_processes(limit=2, processes=procs)[0].name == "heavy"


def test_vanished_processes_are_skipped():
    procs = [VanishedProcess(), FakeProcess(2, "two", 5.0, 1.0)]

    assert [p.name for p in read_top_processes(processes=procs)] == ["two"]


def test_real_machine_reports_processes():
    top = read_top_processes(limit=3)

    assert 1 <= len(top) <= 3
    assert all(p.name for p in top)
    assert all(p.cpu_percent >= 0 for p in top)
