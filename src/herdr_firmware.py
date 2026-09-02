"""Guided flash of the herdr-capable duckyPad EVO firmware.

The Configurator never flashes firmware by itself; it guides the user through
the DFU procedure and, when ``dfu-util`` is present, runs the exact command
against a **verified** ``.dfu`` image. The verified image is the
``v3.1.0-herdr`` build that ships in the duckyPad repo.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# Verified herdr-capable image (duckyPad repo, commit e6738101).
HERDR_DFU_NAME = "duckypad_v3.1.0-herdr.dfu"
HERDR_DFU_SHA256 = "b1ea7431f40045da1cb80e6188df81b11ec9016c76af7ebbd0e897be3b18da96"
# Stock rollback image (duckyPad repo).
STOCK_DFU_NAME = "duckypad_v3.0.4.dfu"
STOCK_DFU_SHA256 = "f6d8220f88df15da374c2bb1d45bae711fd0f080678b44f9177e3173ded9fa3d"

DFU_UTIL_DEVICE = "0483:df11"


class FirmwareError(RuntimeError):
    pass


@dataclass
class FirmwareImage:
    name: str
    path: Path
    sha256: str
    expected_sha256: str | None

    @property
    def verified(self) -> bool:
        return self.expected_sha256 is None or self.sha256 == self.expected_sha256


def _find_repo_firmware(name: str) -> Path | None:
    for base in (Path.home() / "Projects" / "duckyPad", Path.home() / "duckyPad"):
        candidate = base / "firmware" / name
        if candidate.is_file():
            return candidate
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def herdr_image() -> FirmwareImage:
    path = _find_repo_firmware(HERDR_DFU_NAME)
    if path is None:
        raise FirmwareError(f"{HERDR_DFU_NAME} not found in the duckyPad repo (run `git pull`).")
    return FirmwareImage(
        name=HERDR_DFU_NAME,
        path=path,
        sha256=sha256_of(path),
        expected_sha256=HERDR_DFU_SHA256,
    )


def stock_image() -> FirmwareImage | None:
    path = _find_repo_firmware(STOCK_DFU_NAME)
    if path is None:
        return None
    return FirmwareImage(
        name=STOCK_DFU_NAME,
        path=path,
        sha256=sha256_of(path),
        expected_sha256=STOCK_DFU_SHA256,
    )


def flash_command(image: FirmwareImage) -> list[str]:
    if not shutil.which("dfu-util"):
        raise FirmwareError("dfu-util is not installed — the guided flash cannot run.")
    if not image.verified:
        raise FirmwareError(
            f"SHA-256 mismatch for {image.name}: got {image.sha256}, "
            f"expected {image.expected_sha256}. Refusing to flash."
        )
    return ["dfu-util", f"--device={DFU_UTIL_DEVICE}", "-a", "0", "-D", str(image.path)]


def flash(image: FirmwareImage, on_progress=None) -> str:
    """Flash ``image`` to a pad in DFU mode. Caller must confirm DFU mode first."""
    cmd = flash_command(image)
    collected: list[str] = []
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    for line in output.splitlines():
        collected.append(line)
        if on_progress:
            on_progress(line)
    if proc.returncode != 0:
        raise FirmwareError(f"dfu-util exited with status {proc.returncode}.\n{output}")
    return output
