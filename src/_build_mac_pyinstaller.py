from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import PyInstaller.__main__

if sys.platform != "darwin":
    raise SystemExit("this script is for macOS only")

ROOT = Path.cwd()
APP_NAME = "duckyPad Configurator"
BUNDLE_ID = "com.dekunukem.duckypad-configurator"


def version() -> str:
    for line in (ROOT / "duckypad_config.py").read_text(encoding="utf-8").splitlines():
        if "THIS_VERSION_NUMBER =" in line:
            return line.split("'")[-2]
    raise RuntimeError("could not find THIS_VERSION_NUMBER")


def clean(paths: list[Path]) -> None:
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def build_icns(source: Path, output: Path) -> None:
    iconset = ROOT / "build" / "duckyPad.iconset"
    iconset.mkdir(parents=True)
    for size in (16, 32, 128, 256, 512):
        for suffix, pixels in (("", size), ("@2x", size * 2)):
            subprocess.run(
                ["sips", "-z", str(pixels), str(pixels), str(source), "--out", str(iconset / f"icon_{size}x{size}{suffix}.png")],
                check=True,
                stdout=subprocess.DEVNULL,
            )
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True)


this_version = version()
bundle_name = "duckyPad Configurator"
dmg_name = ROOT / f"duckyPad-Configurator_{this_version}_macOS_ARM64.dmg"
stage = ROOT / "dmg-root"
clean([ROOT / "build", ROOT / "dist", stage, dmg_name])

icon_path = ROOT / "build" / "duckyPad.icns"
build_icns(ROOT / "_icon_512.png", icon_path)

PyInstaller.__main__.run([
    "duckypad_config.py",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    f"--name={bundle_name}",
    f"--icon={icon_path}",
    f"--osx-bundle-identifier={BUNDLE_ID}",
    "--add-data=_icon_512.png:.",
    "--collect-all=certifi",
])

app_bundle = ROOT / "dist" / f"{bundle_name}.app"
if not app_bundle.is_dir():
    raise RuntimeError(f"missing macOS app bundle: {app_bundle}")
stage.mkdir()
shutil.copytree(app_bundle, stage / app_bundle.name)
os.symlink("/Applications", stage / "Applications")
(stage / "README.txt").write_text(
    "Drag duckyPad Configurator to Applications, then launch it.\n\n"
    "https://dekunukem.github.io/duckyPad-Pro/doc/linux_macos_notes.html\n",
    encoding="utf-8",
)
subprocess.run(
    [
        "hdiutil",
        "create",
        "-volname",
        APP_NAME,
        "-srcfolder",
        str(stage),
        "-ov",
        "-format",
        "UDZO",
        str(dmg_name),
    ],
    check=True,
)
print(dmg_name)
this_version = version()
bundle_name = "duckyPad Configurator"
icon_path = ROOT / "build" / "duckyPad.icns"
clean([ROOT / "build", ROOT / "dist", stage, dmg_name])
build_icns(ROOT / "_icon_512.png", icon_path)

PyInstaller.__main__.run([
    "duckypad_config.py",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    f"--name={bundle_name}",
    f"--icon={icon_path}",
    f"--osx-bundle-identifier={BUNDLE_ID}",
    "--add-data=_icon_512.png:.",
    "--collect-all=certifi",
])

app_bundle = ROOT / "dist" / f"{bundle_name}.app"
if not app_bundle.is_dir():
    raise RuntimeError(f"missing macOS app bundle: {app_bundle}")
stage.mkdir()
shutil.copytree(app_bundle, stage / app_bundle.name)
os.symlink("/Applications", stage / "Applications")
(stage / "README.txt").write_text(
    "Drag duckyPad Configurator to Applications, then launch it.\n\n"
    "https://dekunukem.github.io/duckyPad-Pro/doc/linux_macos_notes.html\n",
    encoding="utf-8",
)
subprocess.run(
    [
        "hdiutil",
        "create",
        "-volname",
        APP_NAME,
        "-srcfolder",
        str(stage),
        "-ov",
        "-format",
        "UDZO",
        str(dmg_name),
    ],
    check=True,
)
print(dmg_name)
