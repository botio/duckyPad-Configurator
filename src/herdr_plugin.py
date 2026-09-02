"""Installer / upgrader for the duckyPad herdr plugin.

Wraps the plugin's own ``install.sh`` (build + ``herdr plugin link`` +
user service) and streams its output so the Configurator can show progress
and fail with an actionable message. Idempotent: safe to re-run after
``git pull``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from herdr_env import ToolStatus, probe


class PluginInstallError(RuntimeError):
    def __init__(self, message: str, output: str) -> None:
        super().__init__(message)
        self.output = output


@dataclass
class InstallResult:
    ok: bool
    output: str
    service: str


def _resolve_install_script(repo: Path) -> Path:
    script = repo / "install.sh"
    if not script.is_file():
        raise PluginInstallError(
            f"install.sh not found in {repo} — run `git pull` in the duckyPad repo.",
            "",
        )
    return script


def _service_name() -> str:
    if sys.platform == "darwin":
        return "launchd com.botio.ducky-pad-bridge"
    return "systemd user ducky-pad-bridge"


def install_plugin(
    repo: Path | None = None,
    on_progress=None,
) -> InstallResult:
    """Run the plugin's installer. ``on_progress(line)`` receives each output line."""
    env = probe() if repo is None else None
    repo = repo or (env.plugin_repo if env else None)
    if repo is None:
        raise PluginInstallError(
            "Could not locate the duckyPad repo containing herdr-ducky-pad/.",
            "",
        )
    env = probe()
    if not env.cargo.ok:
        raise PluginInstallError(
            "The Rust toolchain (cargo) is required to build the plugin. Install via https://rustup.rs.",
            env.cargo.detail,
        )
    if not env.herdr.ok:
        raise PluginInstallError(
            "herdr is required to register the plugin. Install from https://herdr.dev.",
            env.herdr.detail,
        )

    script = _resolve_install_script(repo)
    cmd = ["bash", str(script)]
    collected: list[str] = []
    try:
        with subprocess.Popen(
            cmd,
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as proc:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                collected.append(line)
                if on_progress:
                    on_progress(line)
            returncode = proc.wait()
    except FileNotFoundError as exc:
        raise PluginInstallError(f"Failed to start installer: {exc}", "\n".join(collected))
    output = "\n".join(collected)
    if returncode != 0:
        raise PluginInstallError(
            f"install.sh exited with status {returncode}.",
            output,
        )
    return InstallResult(ok=True, output=output, service=_service_name())


def uninstall_service() -> str:
    """Best-effort stop+disable of the user service. Returns a status line."""
    if sys.platform == "darwin":
        try:
            import subprocess as _sp
            _sp.run(
                ["launchctl", "bootout", f"gui/{os.getuid()}", "com.botio.ducky-pad-bridge"],
                check=False,
                capture_output=True,
            )
            plist = Path.home() / "Library/LaunchAgents/com.botio.ducky-pad-bridge.plist"
            if plist.exists():
                plist.unlink()
            return "launchd service removed"
        except OSError as exc:
            return f"launchctl unavailable ({exc})"
    try:
        import subprocess as _sp
        _sp.run(["systemctl", "--user", "disable", "--now", "ducky-pad-bridge"], check=False, capture_output=True)
        unit = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "systemd/user/ducky-pad-bridge.service"
        if unit.exists():
            unit.unlink()
        return "systemd user service removed"
    except OSError as exc:
        return f"systemctl unavailable ({exc})"
