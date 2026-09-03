from __future__ import annotations

from pathlib import Path
import shutil
import sys

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT = REPO / "build" / "duckypad-core"


def clean(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


clean(OUTPUT)
clean(ROOT / "build-sidecar")
PyInstaller.__main__.run([
    str(ROOT / "core" / "sidecar.py"),
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name=duckypad_core",
    f"--distpath={REPO / 'build'}",
    f"--workpath={ROOT / 'build-sidecar'}",
    f"--specpath={ROOT / 'build-sidecar'}",
    "--collect-all=certifi",
    "--hidden-import=hid",
    "--hidden-import=psutil",
    "--hidden-import=herdr",
    "--hidden-import=herdr_config",
    "--hidden-import=herdr_env",
    "--hidden-import=herdr_firmware",
    "--hidden-import=herdr_plugin",
    "--hidden-import=dsvm_common",
    "--hidden-import=dsvm_make_bytecode",
    "--hidden-import=dsvm_preprocessor",
    "--hidden-import=dsvm_ds2py",
    "--hidden-import=dsvm_myast",
    "--hidden-import=dsvm_optimizer",
    "--hidden-import=duck_objs",
    "--hidden-import=check_update",
    "--exclude-module=tkinter",
])

generated = REPO / "build" / "duckypad_core"
if generated != OUTPUT and generated.is_dir():
    generated.rename(OUTPUT)

if not (OUTPUT / ("duckypad_core.exe" if sys.platform == "win32" else "duckypad_core")).exists():
    raise RuntimeError(f"PyInstaller output missing: {OUTPUT}")

if sys.platform == "darwin":
    # The sidecar is a standalone Mach-O tree that macOS treats separately from
    # the Electron .app. An unsigned sidecar can have its HID/IOKit access
    # denied even when the app itself is signed, so ad-hoc sign every native
    # image in the bundle before it ships inside the DMG.
    import subprocess
    native_images = [
        OUTPUT / "duckypad_core",
        *(OUTPUT.rglob("*.so")),
        *(OUTPUT.rglob("*.dylib")),
        *(OUTPUT.rglob("*.bundle")),
    ]
    for image in sorted(set(native_images)):
        if not image.exists():
            continue
        completed = subprocess.run(
            ["codesign", "--force", "--sign", "-", str(image)],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"codesign failed for {image}: {completed.stderr}")
        verify = subprocess.run(
            ["codesign", "--verify", "--strict", str(image)],
            capture_output=True,
            text=True,
        )
        if verify.returncode != 0:
            raise RuntimeError(f"codesign verify failed for {image}: {verify.stderr}")

print(OUTPUT)
