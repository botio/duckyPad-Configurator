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
import sys
from dataclasses import dataclass, field
from pathlib import Path


HERDR_MIN_VERSION = "0.8.0"
BRIDGE_LABEL = "com.botio.ducky-pad-bridge"
BRIDGE_SERVICE = "ducky-pad-bridge"


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
    herdr_socket: Path | None = None
    herdr_socket_ok: bool = False
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
            f"herdr socket: {self.herdr_socket if self.herdr_socket else 'unknown'}"
            + f" ({'OK' if self.herdr_socket_ok else 'MISSING — start herdr'})",
        ]
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


def _probe_env() -> dict[str, str]:
    """Electron/GUI apps often have a stripped PATH; put common tool dirs first."""
    env = os.environ.copy()
    extras = [
        str(Path.home() / ".cargo" / "bin"),
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
    ]
    path = env.get("PATH", "")
    for item in reversed(extras):
        if item and item not in path.split(os.pathsep):
            path = item + os.pathsep + path
    env["PATH"] = path
    return env


def _run(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_probe_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _which(name: str) -> str | None:
    env = _probe_env()
    return shutil.which(name, path=env.get("PATH"))


def _version(stdout: str) -> str | None:
    for line in stdout.splitlines():
        parts = line.strip().split()
        for part in parts:
            if part[:1].isdigit() and "." in part:
                return part.strip(",;")
    return None


def _parse_version(v: str) -> tuple[int, ...]:
    out: list[int] = []
    for part in v.replace("-", ".").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            out.append(int(digits))
    return tuple(out) or (0,)


def check_herdr() -> ToolStatus:
    if not _which("herdr"):
        return ToolStatus(
            "herdr",
            False,
            detail="not on PATH (GUI apps need Homebrew / ~/.local/bin)",
        )
    proc = _run(["herdr", "--version"], timeout=10)
    version = _version(proc.stdout) if proc and proc.stdout else None
    if version and _parse_version(version) < _parse_version(HERDR_MIN_VERSION):
        return ToolStatus(
            "herdr",
            True,
            version,
            detail=f"found {version}, want >={HERDR_MIN_VERSION}",
        )
    return ToolStatus("herdr", True, version)


def check_cargo() -> ToolStatus:
    if not _which("cargo"):
        return ToolStatus("cargo", False, detail="not on PATH")
    proc = _run(["cargo", "--version"])
    return ToolStatus("cargo", True, _version(proc.stdout) if proc else None)


def check_dfu_util() -> ToolStatus:
    if not _which("dfu-util"):
        return ToolStatus("dfu-util", False, detail="not on PATH")
    proc = _run(["dfu-util", "--version"])
    first = (proc.stdout.splitlines()[0] if proc and proc.stdout else "") or None
    return ToolStatus("dfu-util", True, first)


def _config_root() -> Path:
    """Platform config root (same convention as Rust dirs::config_dir)."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base)
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def herdr_socket_candidates() -> list[Path]:
    """Paths the bridge may use to talk to herdr."""
    base = _config_root() / "herdr"
    out: list[Path] = []
    env_path = os.environ.get("HERDR_SOCKET_PATH")
    if env_path:
        out.append(Path(env_path))
    session = os.environ.get("HERDR_SESSION")
    if session:
        out.append(base / "sessions" / session / "herdr.sock")
    out.append(base / "herdr.sock")
    sessions = base / "sessions"
    if sessions.is_dir():
        try:
            for child in sorted(sessions.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                sock = child / "herdr.sock"
                if sock not in out:
                    out.append(sock)
        except OSError:
            pass
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "herdr" / "herdr.sock"
    if xdg not in out:
        out.append(xdg)
    return out


def find_herdr_socket() -> tuple[Path | None, bool]:
    """Return (preferred path, exists)."""
    preferred: Path | None = None
    for path in herdr_socket_candidates():
        if preferred is None:
            preferred = path
        try:
            if path.exists():
                return path, True
        except OSError:
            continue
    return preferred, False


def find_plugin_repo() -> Path | None:
    """Locate a checkout containing herdr-plugin.toml."""
    home = Path.home()
    candidates = [
        home / "Projects" / "duckyPad" / "herdr-ducky-pad",
        home / "projects" / "duckyPad" / "herdr-ducky-pad",
        home / "Developer" / "duckyPad" / "herdr-ducky-pad",
        home / "src" / "duckyPad" / "herdr-ducky-pad",
        home / "duckyPad" / "herdr-ducky-pad",
        home / "Projects" / "herdr-ducky-pad",
        Path(__file__).resolve().parents[2] / "duckyPad" / "herdr-ducky-pad",
        Path(__file__).resolve().parents[1] / "herdr-ducky-pad",
    ]
    plugins = _config_root() / "herdr" / "plugins.json"
    if plugins.is_file():
        try:
            payload = json.loads(plugins.read_text(encoding="utf-8"))
            items = payload if isinstance(payload, list) else payload.get("plugins", [])
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                plugin_id = str(item.get("plugin_id") or item.get("id") or "")
                if plugin_id and plugin_id not in {"ducky.pad-bridge", "ducky-pad-bridge"}:
                    if "ducky" not in plugin_id.lower() and "pad" not in plugin_id.lower():
                        continue
                root = item.get("plugin_root") or item.get("root") or item.get("path")
                if root:
                    candidates.insert(0, Path(str(root)))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    for candidate in candidates:
        try:
            if (candidate / "herdr-plugin.toml").is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def check_plugin_registered(repo: Path | None) -> bool:
    """True when herdr lists a linked ducky pad bridge plugin."""
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
        if not isinstance(item, dict):
            continue
        plugin_id = str(item.get("plugin_id") or item.get("id") or "")
        if plugin_id not in {"ducky.pad-bridge", "ducky-pad-bridge"}:
            continue
        if repo is not None:
            root = item.get("plugin_root") or item.get("root") or item.get("path")
            if root and Path(str(root)).resolve() != repo.resolve():
                continue
        return True
    return False


def check_service_running() -> bool:
    """True when the ducky-pad-bridge user service appears alive."""
    proc = _run(["systemctl", "--user", "is-active", BRIDGE_SERVICE], timeout=8)
    if proc is not None and proc.stdout.strip() == "active":
        return True
    proc = _run(["launchctl", "list"], timeout=8)
    if proc is not None and proc.stdout:
        for line in proc.stdout.splitlines():
            if BRIDGE_LABEL not in line and "ducky-pad-bridge" not in line:
                continue
            parts = line.split()
            if parts and parts[0] not in {"-", "0"}:
                return True
    proc = _run(["pgrep", "-fl", "ducky-pad-bridge"], timeout=5)
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return True
    return False


def probe() -> HerdrEnv:
    sock, sock_ok = find_herdr_socket()
    env = HerdrEnv(
        herdr=check_herdr(),
        cargo=check_cargo(),
        dfu_util=check_dfu_util(),
        plugin_repo=find_plugin_repo(),
        herdr_socket=sock,
        herdr_socket_ok=sock_ok,
    )
    env.plugin_installed = check_plugin_registered(env.plugin_repo)
    env.service_running = check_service_running()
    if not env.herdr.ok:
        env.notes.append("Install herdr and ensure it is on PATH for the GUI app (Homebrew / ~/.local/bin).")
    if not env.cargo.ok:
        env.notes.append("The plugin is written in Rust; install rustup to build it.")
    if not env.dfu_util.ok:
        env.notes.append("Without dfu-util the guided firmware flash falls back to manual steps.")
    if env.plugin_repo is None:
        env.notes.append("herdr-ducky-pad/ not found under ~/Projects/duckyPad — clone it and run install.sh.")
    if not env.herdr_socket_ok:
        env.notes.append(
            "herdr.sock is missing — start the herdr app/server first. "
            "Bridge logs 'connect …/herdr.sock' until herdr creates it. "
            f"Expected: {env.herdr_socket}"
        )
    if env.service_running and not env.herdr_socket_ok:
        env.notes.append("Bridge is running but cannot talk to herdr; lights/OLED stay idle until herdr is up.")
    if not env.service_running and env.plugin_repo is not None:
        env.notes.append("Bridge service not detected. macOS: launchctl list | grep ducky-pad-bridge; re-run install.sh.")
    return env
