"""Herdr / Rust / DFU environment diagnostics for the Configurator's
herdr-integration menu.

Everything here is read-only: it only probes what is present on the host and
reports human-readable status, never installs or mutates anything.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


HERDR_MIN_VERSION = "0.8.0"


@dataclass
class ToolStatus:
    name: str
    found: bool
    version: str | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.found


@dataclass
class HerdrEnv:
    herdr: ToolStatus
    cargo: ToolStatus
    dfu_util: ToolStatus
    plugin_repo: Path | None = None
    plugin_installed: bool = False
    service_running: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def can_install_plugin(self) -> bool:
        return self.cargo.ok and self.herdr.ok

    def summary(self) -> str:
        lines = [
            f"herdr:  {'OK ' + (self.herdr.version or '') if self.herdr.ok else 'MISSING'}"
            + (f"  ({self.herdr.detail})" if not self.herdr.ok and self.herdr.detail else ""),
            f"cargo:  {'OK ' + (self.cargo.version or '') if self.cargo.ok else 'MISSING'}"
            + (f"  ({self.cargo.detail})" if not self.cargo.ok and self.cargo.detail else ""),
            f"dfu-util: {'OK' if self.dfu_util.ok else 'MISSING'}",
            f"plugin repo: {self.plugin_repo if self.plugin_repo else 'not found'}",
            f"plugin registered with herdr: {self.plugin_installed}",
            f"user service running: {self.service_running}",
        ]
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


def _run(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _version(stdout: str) -> str | None:
    # herdr / cargo print "<tool> x.y.z ..." on the first line
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1][:1].isdigit():
            return parts[1]
    return None


def _parse_version(v: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in v.split(".")[:3]:
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits:
            out.append(int(digits))
        else:
            break
    return tuple(out) or (0,)


def check_herdr() -> ToolStatus:
    if not shutil.which("herdr"):
        return ToolStatus("herdr", False, detail="`herdr` not on PATH — install from https://herdr.dev")
    proc = _run(["herdr", "--version"])
    if proc is None:
        return ToolStatus("herdr", True, detail="present but did not report a version")
    version = _version(proc.stdout)
    if version and _parse_version(version) < _parse_version(HERDR_MIN_VERSION):
        return ToolStatus("herdr", True, version, f"below required {HERDR_MIN_VERSION}")
    return ToolStatus("herdr", True, version)


def check_cargo() -> ToolStatus:
    if not shutil.which("cargo"):
        return ToolStatus("cargo", False, detail="Rust toolchain missing — see https://rustup.rs")
    proc = _run(["cargo", "--version"])
    return ToolStatus("cargo", True, _version(proc.stdout) if proc else None)


def check_dfu_util() -> ToolStatus:
    if not shutil.which("dfu-util"):
        return ToolStatus("dfu-util", False, detail="needed for guided firmware flash")
    proc = _run(["dfu-util", "--version"])
    first = proc.stdout.splitlines()[0].strip() if proc and proc.stdout else None
    return ToolStatus("dfu-util", True, first)


def find_plugin_repo() -> Path | None:
    """Locate a checkout of the duckyPad repo containing the herdr plugin."""
    candidates = [
        Path.home() / "Projects" / "duckyPad" / "herdr-ducky-pad",
        Path.home() / "duckyPad" / "herdr-ducky-pad",
    ]
    for candidate in candidates:
        if (candidate / "herdr-plugin.toml").exists():
            return candidate
    return None


def _config_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base)
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def check_plugin_registered(repo: Path | None) -> bool:
    """True when herdr lists a linked ``ducky.pad-bridge`` plugin."""
    proc = _run(["herdr", "plugin", "list", "--json"], timeout=15)
    if proc is None or not proc.stdout:
        return False
    try:
        payload = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        return False
    result = payload.get("result", payload)
    items = result.get("plugins", []) if isinstance(result, dict) else []
    for item in items:
        if not isinstance(item, dict) or item.get("plugin_id") != "ducky.pad-bridge":
            continue
        if repo is not None:
            root = item.get("plugin_root")
            if root and Path(root).resolve() != repo.resolve():
                continue
        return True
    return False


def check_service_running() -> bool:
    proc = _run(["systemctl", "--user", "is-active", "ducky-pad-bridge"], timeout=8)
    if proc is not None and proc.stdout.strip() == "active":
        return True
    proc = _run(["launchctl", "list"], timeout=8)
    if proc is not None:
        for line in proc.stdout.splitlines():
            if "com.botio.ducky-pad-bridge" in line:
                return True
    return False


def probe() -> HerdrEnv:
    env = HerdrEnv(
        herdr=check_herdr(),
        cargo=check_cargo(),
        dfu_util=check_dfu_util(),
        plugin_repo=find_plugin_repo(),
    )
    env.plugin_installed = check_plugin_registered(env.plugin_repo)
    env.service_running = check_service_running()
    if not env.herdr.ok:
        env.notes.append("Install herdr to let the Configurator register the plugin.")
    if not env.cargo.ok:
        env.notes.append("The plugin is written in Rust; install the Rust toolchain (rustup) to build it.")
    if not env.dfu_util.ok:
        env.notes.append("Without dfu-util the guided firmware flash will fall back to manual instructions.")
    if env.plugin_repo is None:
        env.notes.append("duckyPad repo (with herdr-ducky-pad/) not found; cloning it makes the plugin available.")
    return env
