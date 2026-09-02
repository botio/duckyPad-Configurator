"""High-level herdr integration for the duckyPad Configurator.

Combines environment diagnostics (``herdr_env``), plugin install/upgrade
(``herdr_plugin``), LED/mapping configuration (``herdr_config``) and guided
firmware flashing (``herdr_firmware``) into a single API the Tkinter menu
can call.

Public entry point: :func:`herdr_status` and the ``HerdrIntegration``
class used by the GUI.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from herdr_config import HerdrConfig, config_path, load, save
from herdr_env import HerdrEnv, probe
from herdr_firmware import (
    FirmwareError,
    herdr_image,
    stock_image,
    flash_command,
)
from herdr_plugin import InstallResult, install_plugin, uninstall_service


@dataclass
class IntegrationStatus:
    env: HerdrEnv
    config: HerdrConfig
    herdr_dfu_verified: bool | None = None

    def ready_to_install(self) -> bool:
        return self.env.can_install_plugin


def herdr_status() -> IntegrationStatus:
    """One-shot, read-only status for the menu's banner."""
    env = probe()
    cfg = load()
    verified: bool | None = None
    try:
        verified = herdr_image().verified
    except FirmwareError:
        verified = None
    return IntegrationStatus(env=env, config=cfg, herdr_dfu_verified=verified)


class HerdrIntegration:
    """Facade used by the Configurator's herdr menu."""

    def status(self) -> IntegrationStatus:
        return herdr_status()

    def install(self, on_progress=None) -> InstallResult:
        return install_plugin(on_progress=on_progress)

    def uninstall(self) -> str:
        return uninstall_service()

    def save_config(self, config: HerdrConfig) -> Path:
        return save(config)

    def load_config(self) -> HerdrConfig:
        return load()

    def config_file(self) -> Path:
        return config_path()

    def firmware_flash_command(self) -> str:
        return " ".join(flash_command(herdr_image()))

    def stock_flash_command(self) -> str | None:
        image = stock_image()
        if image is None:
            return None
        return " ".join(flash_command(image))

    def open_config_file(self) -> bool:
        """Open the herdr.json config in the platform editor. Returns True on success."""
        path = config_path()
        if not path.exists():
            save(HerdrConfig())
        if _system_open(path):
            return True
        return False


def _system_open(path: Path) -> bool:
    import sys
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return True
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
            return True
    except OSError:
        return False
    return False


def show_diagnostics() -> str:
    """Return a human-readable multi-line status block for the GUI log window."""
    status = herdr_status()
    env = status.env
    lines = ["== herdr environment =="]
    lines.append(env.summary())
    lines.append("")
    lines.append("== configuration ==")
    lines.append(f"  config file: {config_path()}")
    if status.config.colors:
        lines.append(f"  palette overrides: {list(status.config.colors)}")
    else:
        lines.append("  palette: builtin (no overrides)")
    if status.config.pinned_slots:
        lines.append(f"  pinned slots: {status.config.pinned_slots}")
    else:
        lines.append("  slot mapping: sticky (pane_id-based)")
    lines.append("")
    lines.append("== firmware ==")
    if status.herdr_dfu_verified is True:
        lines.append("  herdr-capable .dfu: verified (SHA-256 matches)")
        lines.append(f"  flash: {HerdrIntegration().firmware_flash_command()}")
    elif status.herdr_dfu_verified is False:
        lines.append("  herdr-capable .dfu: SHA-256 MISMATCH — do not flash")
    else:
        lines.append("  herdr-capable .dfu: not found (git pull the duckyPad repo)")
    stock = HerdrIntegration().stock_flash_command()
    if stock:
        lines.append(f"  rollback: {stock}")
    return "\n".join(lines)
