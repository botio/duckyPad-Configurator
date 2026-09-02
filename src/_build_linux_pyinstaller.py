from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from urllib.request import urlretrieve

import PyInstaller.__main__

if sys.platform != "linux":
    raise SystemExit("this script is for Linux only")

ROOT = Path.cwd()
APP_NAME = "duckyPad-Configurator"
LINUXDEPLOY_VERSION = "1-alpha-20251107-1"
LINUXDEPLOY_URL = (
    "https://github.com/linuxdeploy/linuxdeploy/releases/download/"
    f"{LINUXDEPLOY_VERSION}/linuxdeploy-x86_64.AppImage"
)


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


def linuxdeploy_path() -> Path:
    configured = os.environ.get("LINUXDEPLOY")
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"LINUXDEPLOY does not exist: {path}")
        return path

    path = ROOT / ".tools" / "linuxdeploy-x86_64.AppImage"
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        print(f"Downloading linuxdeploy {LINUXDEPLOY_VERSION}")
        urlretrieve(LINUXDEPLOY_URL, path)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def appimage_plugin(linuxdeploy: Path) -> Path:
    extract_dir = ROOT / ".tools" / "linuxdeploy-root"
    plugin = extract_dir / "squashfs-root" / "usr" / "bin" / "linuxdeploy-plugin-appimage"
    if plugin.exists():
        return plugin

    clean([extract_dir])
    extract_dir.mkdir(parents=True)
    extraction_env = os.environ | {"APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run([str(linuxdeploy), "--appimage-extract"], cwd=extract_dir, env=extraction_env, check=True)
    if not plugin.exists():
        raise RuntimeError(f"linuxdeploy did not provide an AppImage output plugin: {plugin}")
    return plugin


this_version = version()
bundle_name = f"duckyPad_Configurator_{this_version.replace('.', '_')}_linux_x86_64"
app_dir = ROOT / "AppDir"
final_appimage = ROOT / f"duckyPad-Configurator_{this_version}_x86_64.AppImage"
clean([
    ROOT / "build",
    ROOT / "dist",
    app_dir,
    ROOT / "duckyPad_Configurator-x86_64.AppImage",
    *ROOT.glob("duckyPad-Configurator_*_x86_64.AppImage"),
])

# uv-managed CPython keeps Tcl/Tk beside the interpreter rather than on the
# dynamic loader path. Bundle those exact shared objects for the frozen GUI.
pylib = Path(sys.executable).resolve().parents[1] / "lib"
tcl_binaries = [
    f"--add-binary={library}:."
    for library in (pylib / "libtcl9.0.so", pylib / "libtcl9tk9.0.so")
    if library.exists()
]

PyInstaller.__main__.run([
    "duckypad_config.py",
    "--noconfirm",
    "--clean",
    "--onedir",
    f"--name={bundle_name}",
    "--icon=_icon.ico",
    "--add-data=_icon_512.png:.",
    "--collect-all=certifi",
] + tcl_binaries)

bundle_dir = ROOT / "dist" / bundle_name
app_dir.mkdir()
lib_dir = app_dir / "usr" / "lib" / "duckypad-configurator"
lib_dir.parent.mkdir(parents=True)
shutil.copytree(bundle_dir, lib_dir)

bin_dir = app_dir / "usr" / "bin"
bin_dir.mkdir(parents=True)
launcher = bin_dir / "duckyPad-Configurator"
launcher.write_text(
    "#!/bin/sh\n"
    "HERE=$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd)\n"
    f"exec \"$HERE/../lib/duckypad-configurator/{bundle_name}\" \"$@\"\n",
    encoding="utf-8",
)
launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

applications_dir = app_dir / "usr" / "share" / "applications"
icons_dir = app_dir / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
applications_dir.mkdir(parents=True)
icons_dir.mkdir(parents=True)
shutil.copy2(ROOT / "_icon_512.png", icons_dir / "duckyPad-Configurator.png")
(applications_dir / "duckyPad-Configurator.desktop").write_text(
    "[Desktop Entry]\n"
    "Type=Application\n"
    "Name=duckyPad Configurator\n"
    "Comment=Configure duckyPad profiles and duckyScript keys\n"
    "Exec=duckyPad-Configurator\n"
    "Icon=duckyPad-Configurator\n"
    "Categories=Utility;Settings;\n"
    "Terminal=false\n",
    encoding="utf-8",
)

desktop_file = applications_dir / "duckyPad-Configurator.desktop"
icon_file = icons_dir / "duckyPad-Configurator.png"
shutil.copy2(desktop_file, app_dir / desktop_file.name)
shutil.copy2(icon_file, app_dir / icon_file.name)
(app_dir / "AppRun").write_text(
    "#!/bin/sh\nexec \"$APPDIR/usr/bin/duckyPad-Configurator\" \"$@\"\n",
    encoding="utf-8",
)
(app_dir / "AppRun").chmod((app_dir / "AppRun").stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
(app_dir / "README.txt").write_text(
    "duckyPad Configurator for Linux\n\n"
    "Run this AppImage directly. If your distribution requires it, mark it executable first.\n"
    "https://dekunukem.github.io/duckyPad-Pro/doc/linux_macos_notes.html\n",
    encoding="utf-8",
)

linuxdeploy = linuxdeploy_path()
plugin = appimage_plugin(linuxdeploy)
appimage_env = os.environ | {"ARCH": "x86_64"}
subprocess.run([str(plugin), "--appdir", str(app_dir)], env=appimage_env, check=True)

appimages = list(ROOT.glob("*.AppImage"))
if len(appimages) != 1:
    raise RuntimeError(f"expected one AppImage output, found: {appimages}")
appimages[0].replace(final_appimage)
print(final_appimage)
