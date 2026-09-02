"""User configuration for the duckyPad herdr plugin.

The plugin's daemon currently hard-codes its state->color palette
(``model.rs``). This module owns a portable, schema-versioned config file
that the Configurator writes and that the plugin can later read to
override the palette and to pin an explicit slot -> agent mapping.

Config location:
    ~/.config/duckyPad/herdr.json        (Linux)
    ~/Library/Application Support/duckyPad/herdr.json   (macOS)

The file is optional: when absent, the plugin keeps its built-in palette and
sticky (pane_id-based) slot assignment.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# Built-in palette from the plugin's model.rs (locked defaults).
BUILTIN_PALETTE: dict[str, tuple[int, int, int]] = {
    "blocked": (255, 0, 0),
    "working": (0, 255, 0),
    "done": (0, 0, 255),
    "unknown": (255, 165, 0),
    "idle": (48, 48, 48),
}


def _config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "duckyPad"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "duckyPad"


def config_path() -> Path:
    return _config_dir() / "herdr.json"


@dataclass
class HerdrConfig:
    schema_version: int = SCHEMA_VERSION
    # state name -> [r, g, b]; only keys present override the builtin palette.
    colors: dict[str, list[int]] = field(default_factory=dict)
    # Optional explicit slot (1..15) -> pane_id pinning. When a pane_id is
    # pinned, the plugin must keep that agent on that slot (overriding the
    # sticky lowest-free-slot rule). Unpinned slots use the sticky rule.
    pinned_slots: dict[int, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "colors": self.colors,
            "pinned_slots": {str(k): v for k, v in self.pinned_slots.items()},
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "HerdrConfig":
        version = payload.get("schema_version", SCHEMA_VERSION)
        if version != SCHEMA_VERSION:
            raise ValueError(f"unsupported herdr config schema {version}")
        colors: dict[str, list[int]] = {}
        for name, rgb in payload.get("colors", {}).items():
            if not isinstance(rgb, list) or len(rgb) != 3:
                raise ValueError(f"color for {name!r} must be [r, g, b]")
            if any(not isinstance(c, int) or not 0 <= c <= 255 for c in rgb):
                raise ValueError(f"color for {name!r} has an out-of-range channel")
            colors[name] = rgb
        pinned: dict[int, str] = {}
        for slot, pane in payload.get("pinned_slots", {}).items():
            slot_int = int(slot)
            if not 1 <= slot_int <= 15:
                raise ValueError(f"slot {slot_int} out of range 1..15")
            if not isinstance(pane, str) or not pane:
                raise ValueError(f"slot {slot_int} pane_id must be a non-empty string")
            pinned[slot_int] = pane
        return cls(colors=colors, pinned_slots=pinned)


def load() -> HerdrConfig:
    path = config_path()
    if not path.exists():
        return HerdrConfig()
    return HerdrConfig.from_json(json.loads(path.read_text(encoding="utf-8")))


def save(config: HerdrConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config.to_json(), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


def builtin_colors() -> dict[str, tuple[int, int, int]]:
    return dict(BUILTIN_PALETTE)


def effective_palette(config: HerdrConfig) -> dict[str, tuple[int, int, int]]:
    """Built-in palette with the user's overrides applied."""
    merged = {name: tuple(rgb) for name, rgb in BUILTIN_PALETTE.items()}
    for name, rgb in config.colors.items():
        merged[name] = tuple(rgb)  # type: ignore[assignment]
    return merged
