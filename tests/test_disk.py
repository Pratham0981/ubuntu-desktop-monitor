"""Disk readings: root filesystem plus the whole physical disk it lives on."""

import json
import shutil
import subprocess

import psutil
import pytest

from dashboard.disk import DiskStats, MountUsage, parse_lsblk, read_disk

PAYLOAD = {
    "blockdevices": [
        {
            "name": "nvme0n1",
            "type": "disk",
            "size": 256_060_514_304,
            "fstype": None,
            "mountpoints": [None],
            "pkname": None,
            "children": [
                {"name": "nvme0n1p1", "type": "part", "size": 1_127_219_200,
                 "fstype": "vfat", "mountpoints": ["/boot/efi"], "pkname": "nvme0n1"},
                {"name": "nvme0n1p3", "type": "part", "size": 104_931_000_320,
                 "fstype": "ext4", "mountpoints": ["/"], "pkname": "nvme0n1"},
                {"name": "nvme0n1p4", "type": "part", "size": 96_311_705_600,
                 "fstype": "ext4", "mountpoints": ["/home"], "pkname": "nvme0n1"},
            ],
        },
        {
            "name": "sda",
            "type": "disk",
            "size": 1_000_204_886_016,
            "fstype": None,
            "mountpoints": [None],
            "pkname": None,
            "children": [
                {"name": "sda1", "type": "part", "size": 262_144_000_000,
                 "fstype": "ntfs", "mountpoints": [None], "pkname": "sda"},
            ],
        },
    ]
}

USAGE = {
    "/": (102_683_975_680, 49_505_730_560, 47_914_917_888),
    "/boot/efi": (1_126_149_120, 8_000_000, 1_118_149_120),
    "/home": (94_637_993_984, 30_000_000_000, 60_000_000_000),
}


def fake_usage(mountpoint):
    total, used, free = USAGE[mountpoint]
    return shutil._ntuple_diskusage(total, used, free)


def test_root_row_matches_the_root_filesystem():
    stats = parse_lsblk(PAYLOAD, usage=fake_usage)

    assert stats.root_used == 49_505_730_560
    assert stats.root_total == 102_683_975_680
    assert stats.root_percent == pytest.approx(48.2, abs=0.1)


def test_whole_ssd_covers_every_partition_of_the_root_disk_only():
    stats = parse_lsblk(PAYLOAD, usage=fake_usage)

    # 1.13 GB EFI + 104.9 GB root + 96.3 GB home, all on nvme0n1.
    assert stats.disk_total == 1_127_219_200 + 104_931_000_320 + 96_311_705_600
    assert stats.disk_free == 47_914_917_888 + 1_118_149_120 + 60_000_000_000


def test_unmounted_partitions_count_toward_total_but_not_free():
    payload = {
        "blockdevices": [
            {
                "name": "sda", "type": "disk", "size": 500_000_000_000,
                "mountpoints": [None], "pkname": None,
                "children": [
                    {"name": "sda1", "type": "part", "size": 100_000_000_000,
                     "fstype": "ntfs", "mountpoints": [None], "pkname": "sda"},
                    {"name": "sda2", "type": "part", "size": 200_000_000_000,
                     "fstype": "ext4", "mountpoints": ["/"], "pkname": "sda"},
                ],
            }
        ]
    }

    stats = parse_lsblk(
        payload,
        usage=lambda mount: shutil._ntuple_diskusage(200_000_000_000, 190_000_000_000, 10_000_000_000),
    )

    assert stats.disk_total == 300_000_000_000
    assert stats.disk_free == 10_000_000_000


def test_reading_the_machine_reports_the_root_filesystem():
    stats = read_disk("/")

    real = psutil.disk_usage("/")
    assert isinstance(stats, DiskStats)
    assert stats.root_total == real.total
    assert stats.root_used == real.used
    # The bar's percent must agree with the used/total it is drawn from.
    assert stats.root_percent == pytest.approx(real.used / real.total * 100, abs=0.1)
    assert stats.disk_total >= stats.root_total
    assert 0 <= stats.disk_free <= stats.disk_total


def test_tracked_mounts_are_reported_with_their_own_usage():
    completed = subprocess.CompletedProcess(
        [], 0, stdout=json.dumps(PAYLOAD), stderr=""
    )

    stats = read_disk(
        "/",
        tracked_mounts=("/home",),
        run=lambda *args, **kwargs: completed,
        usage=fake_usage,
    )

    assert stats.mounts == (
        MountUsage(
            mountpoint="/home",
            used=30_000_000_000,
            total=94_637_993_984,
            percent=pytest.approx(31.7, abs=0.1),
        ),
    )


def test_a_tracked_mount_that_is_not_mounted_is_skipped():
    completed = subprocess.CompletedProcess(
        [], 0, stdout=json.dumps(PAYLOAD), stderr=""
    )

    def only_root(mountpoint):
        if mountpoint != "/":
            raise FileNotFoundError(mountpoint)
        return fake_usage(mountpoint)

    stats = read_disk(
        "/",
        tracked_mounts=("/home", "/mnt/models"),
        run=lambda *args, **kwargs: completed,
        usage=only_root,
    )

    assert stats.mounts == ()


def test_real_machine_tracks_home():
    stats = read_disk("/")

    real = psutil.disk_usage("/home")
    home = next(m for m in stats.mounts if m.mountpoint == "/home")
    assert home.total == real.total
    assert home.used == real.used
