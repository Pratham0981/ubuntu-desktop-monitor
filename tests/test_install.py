"""The install script must be user-level, repeatable and leave a working
launcher plus a login autostart entry behind."""

import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INSTALL = REPO / "install.sh"


def run_install(home: Path, **extra_env):
    env = {
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        **extra_env,
    }
    return subprocess.run(
        ["bash", str(INSTALL)],
        cwd=str(home),
        env=env,
        capture_output=True,
        text=True,
    )


def snapshot(root: Path):
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return files


def test_installs_launcher_package_and_autostart_entry(tmp_path):
    result = run_install(tmp_path)

    assert result.returncode == 0, result.stderr
    launcher = tmp_path / ".local/bin/dashboard-widget"
    desktop = tmp_path / "config/autostart/dashboard-widget.desktop"
    package = tmp_path / "data/dashboard-widget/dashboard/__main__.py"
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert desktop.is_file()
    assert package.is_file()

    entry = desktop.read_text()
    assert "Type=Application" in entry
    assert f"Exec={launcher}" in entry
    assert "X-GNOME-Autostart-enabled=true" in entry
    assert "Terminal=false" in entry


def test_running_twice_changes_nothing(tmp_path):
    run_install(tmp_path)
    first = snapshot(tmp_path)

    result = run_install(tmp_path)

    assert result.returncode == 0, result.stderr
    assert snapshot(tmp_path) == first


def test_launcher_hands_over_to_the_package_with_x11_backend(tmp_path):
    stub = tmp_path / "fake-python"
    stub.write_text('#!/bin/sh\necho "$GDK_BACKEND|$@|$PYTHONPATH"\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    run_install(tmp_path, PYTHON=str(stub))

    env = {
        "HOME": str(tmp_path),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }
    result = subprocess.run(
        [str(tmp_path / ".local/bin/dashboard-widget"), "--check"],
        env=env,
        capture_output=True,
        text=True,
    )

    backend, args, pythonpath = result.stdout.strip().split("|")
    assert result.returncode == 0
    assert backend == "x11"
    assert args == "-m dashboard --check"
    assert pythonpath.startswith(str(tmp_path / "data/dashboard-widget"))


def test_install_script_is_user_level():
    script = INSTALL.read_text()

    assert "sudo" not in script
    assert "systemctl" not in script


@pytest.mark.skipif(
    shutil.which("desktop-file-validate") is None, reason="no desktop-file-validate"
)
def test_autostart_entry_passes_desktop_file_validation(tmp_path):
    run_install(tmp_path)

    result = subprocess.run(
        ["desktop-file-validate",
         str(tmp_path / "config/autostart/dashboard-widget.desktop")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
