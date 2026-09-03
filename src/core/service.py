from __future__ import annotations

import base64
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import check_update
import ds_stdlib
import duck_objs
import herdr
import hid_op
import my_compare
from dsvm_common import make_list_of_ds_line_obj_from_str_listing
import dsvm_make_bytecode
import dsvm_preprocessor
from hid_common import DP_MODEL_DUCKYPAD_PRO, DP_MODEL_OG_DUCKYPAD, dp_type
from shared import (
    MAX_KEY_COUNT,
    MAX_PROFILE_NAME_LEN,
    backup_path,
    delete_path,
    ensure_dir,
    make_final_script,
    profile_info_dot_txt,
    stdlib_source_tag_NO_SPACE,
    temp_dir_path,
    unzip_to_own_directory,
    user_header_dot_txt,
    user_header_source_tag_NO_SPACE,
    zip_directory,
)
APP_VERSION = "5.0.6"
DP20_SLOTS = (0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18)
DP20_SLOT_TO_DEVICE = {slot: index + 1 for index, slot in enumerate(DP20_SLOTS)}


class CoreError(Exception):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


def _ts() -> int:
    return int(time.time() * 1000)


def _result(**values: Any) -> dict[str, Any]:
    return {**values, "ts": _ts()}


def _colour(value: Any) -> list[int] | None:
    return list(value) if value is not None else None


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


class CoreService:
    """Device and profile operations shared by the Electron app.

    This class deliberately imports no GUI code. The previous Tk application remains
    intact; its file format and dsvm compiler are reused verbatim here.
    """

    def __init__(self, emit: Callable[[str, dict[str, Any]], None] | None = None):
        self.emit = emit or (lambda _name, _params: None)
        self.device = dp_type()
        self.source = None
        self.root_path: Path | None = None
        self.profile_list: list[duck_objs.dp_profile] = []
        self.user_header: list[str] = []
        self.stdlib_lines: list[str] = self._load_stdlib()
        self.selected_profile: str | None = None
        self.update = {"app": 2, "app_latest": None, "firmware": 2, "firmware_latest": None}

    def dispatch(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        table = {
            "hello": self.hello,
            "device/scan": self.device_scan,
            "device/connect": self.device_connect,
            "device/connect_folder": self.device_connect_folder,
            "device/disconnect": self.device_disconnect,
            "device/reset": self.device_reset,
            "session/state": self.session_state,
            "profiles/get": self.profiles_get,
            "profiles/update": self.profiles_update,
            "profiles/create": self.profiles_create,
            "profiles/rename": self.profiles_rename,
            "profiles/duplicate": self.profiles_duplicate,
            "profiles/delete": self.profiles_delete,
            "profiles/move": self.profiles_move,
            "profiles/select": self.profiles_select,
            "profiles/save": self.profiles_save,
            "profiles/export": self.profiles_export,
            "profiles/import": self.profiles_import,
            "headers/get": self.headers_get,
            "headers/set": self.headers_set,
            "headers/fetch_stdlib": self.headers_fetch_stdlib,
            "script/check": self.script_check,
            "herdr/status": self.herdr_status,
            "herdr/install": self.herdr_install,
            "herdr/uninstall": self.herdr_uninstall,
            "herdr/flash": self.herdr_flash,
            "update/check": self.update_check,
        }
        handler = table.get(method)
        if handler is None:
            raise CoreError(-32601, f"Unknown method: {method}")
        return handler(**params)

    def hello(self) -> dict[str, Any]:
        return _result(
            app_version=APP_VERSION,
            sidecar_version=APP_VERSION,
            platform=sys.platform,
            python=sys.version.split()[0],
            max_profile=64,
            max_keys=MAX_KEY_COUNT,
        )

    def _load_stdlib(self) -> list[str]:
        try:
            return ds_stdlib.get_latest_stdlib_lines(str(Path(backup_path).parent / "dpds_libs"))
        except Exception:
            return []

    def _require_session(self) -> None:
        if self.root_path is None:
            raise CoreError(-32000, "No duckyPad folder is connected")

    @property
    def model(self) -> str:
        return "dp24" if self.device.device_type == DP_MODEL_DUCKYPAD_PRO else "dp20"

    def _model_number(self, model: str) -> int:
        if model == "dp24":
            return DP_MODEL_DUCKYPAD_PRO
        if model == "dp20":
            return DP_MODEL_OG_DUCKYPAD
        raise CoreError(-32002, "model must be dp20 or dp24")

    def _profile_summary(self, profile: duck_objs.dp_profile) -> dict[str, Any]:
        return {
            "name": profile.name,
            "key_count": sum(key is not None for key in profile.keylist),
            "bg_color": _colour(profile.bg_color),
            "landscape": profile.is_landscape,
            "dim_unused": profile.dim_unused,
            "upper_re_halfstep": profile.is_upper_re_halfstep,
            "lower_re_halfstep": profile.is_lower_re_halfstep,
        }

    def _device_summary(self, device: dict[str, Any]) -> dict[str, Any]:
        model_number = device.get("dp_model")
        model = "dp24" if model_number == DP_MODEL_DUCKYPAD_PRO else "dp20"
        drive = self._drive_for_device(device)
        return {
            "id": str(device.get("serial") or device.get("hid_path")),
            "model": model,
            "serial": device.get("serial", ""),
            "fw_version": device.get("fw_version", "unknown"),
            "fw_status": self._firmware_status(device),
            "fw_supported": "unknown",
            "hid_path": str(device.get("hid_path", "")),
            "drive": drive,
        }

    def _firmware_status(self, info: dict[str, Any]) -> str:
        try:
            status = check_update.get_firmware_update_status(info)
        except Exception:
            return "unknown"
        return {0: "ok", 1: "too_low", 2: "unknown"}.get(status, "unknown")

    def _drive_for_device(self, info: dict[str, Any]) -> dict[str, str] | None:
        try:
            hid_msg = info.get("hid_msg")
            if not hid_msg:
                return None
            label = f"DP{hid_msg[6]}_{hid_msg[9]:02X}{hid_msg[10]:02X}"
            mount = hid_op.get_duckypad_drive(label)
            return {"label": label, "mountpoint": mount} if mount else None
        except Exception:
            return None

    def device_scan(self) -> dict[str, Any]:
        try:
            paths = hid_op.get_duckypad_path()
        except (ImportError, OSError) as exc:
            return _result(devices=[], hint="hid_unavailable", detail=str(exc))
        if not paths:
            return _result(devices=[], hint="not_found")
        found, errors = hid_op.probe_duckypad_paths(paths)
        if found:
            return _result(devices=[self._device_summary(device) for device in found], hint=None, probe_errors=errors or None)
        if errors:
            hint = "permissions" if sys.platform == "darwin" else "sudo" if sys.platform.startswith("linux") else "permissions"
            return _result(devices=[], hint=hint, detail=errors[0], compatible_hid_paths=len(paths))
        return _result(devices=[], hint="unresponsive", compatible_hid_paths=len(paths))

    def device_connect(self, id: str) -> dict[str, Any]:
        try:
            found = hid_op.scan_duckypads() or []
        except (ImportError, OSError) as exc:
            raise CoreError(-32001, "Cannot access duckyPad HID device", {"stage": "scan", "detail": str(exc)}) from exc
        info = next((item for item in found if str(item.get("serial") or item.get("hid_path")) == id), None)
        if info is None:
            raise CoreError(-32001, "Selected duckyPad is no longer available", {"stage": "scan"})
        self.device.info_dict = info
        self.device.device_type = info["dp_model"]
        if self.device.device_type == DP_MODEL_DUCKYPAD_PRO:
            drive = self._mount_dp24(info)
            self.device.connection_type = self.device.usbmsc
            return self._connect_folder(Path(drive), "dp24", source="device")
        # The OG has no mounted profile volume. dump_sd produces a local HID mirror.
        import dp20_dumpsd
        dump = Path(backup_path).parent / "hid_dump"
        ensure_dir(str(dump.parent))
        if not dp20_dumpsd.dump_sd(info["hid_path"], str(dump), backup_path, None, None):
            raise CoreError(-32001, "Could not read the duckyPad 2020 profile storage", {"stage": "read"})
        self.device.connection_type = self.device.hidmsg
        return self._connect_folder(dump, "dp20", source="device")

    def _mount_dp24(self, info: dict[str, Any]) -> str:
        existing = self._drive_for_device(info)
        if existing:
            return existing["mountpoint"]
        try:
            hid_op.duckypad_hid_sw_reset(info, reboot_into_usb_msc_mode=True)
        except Exception as exc:
            raise CoreError(-32001, "Could not switch duckyPad into storage mode", {"stage": "reset", "detail": str(exc)}) from exc
        hid_msg = info["hid_msg"]
        label = f"DP{hid_msg[6]}_{hid_msg[9]:02X}{hid_msg[10]:02X}"
        deadline = time.monotonic() + int(os.getenv("DUCKYPAD_MS_TIMEOUT", "20"))
        while time.monotonic() < deadline:
            mount = hid_op.get_duckypad_drive(label)
            if mount:
                return mount
            time.sleep(0.5)
        raise CoreError(-32001, "duckyPad storage volume did not mount in time", {"stage": "mount"})

    def device_connect_folder(self, path: str, model: str) -> dict[str, Any]:
        return self._connect_folder(Path(path), model, source="folder")

    def _connect_folder(self, root: Path, model: str, source: str) -> dict[str, Any]:
        if not root.is_dir():
            raise CoreError(-32004, "Selected profile folder does not exist", {"path": str(root)})
        self.root_path = root.resolve()
        self.source = source
        self.device.device_type = self._model_number(model)
        if source == "folder":
            self.device.connection_type = self.device.local_dir
            self.device.info_dict = None
        self.profile_list = duck_objs.build_profile(str(self.root_path))
        if model == "dp20":
            self._convert_dp20_to_canonical()
        self.user_header = self._read_header(self.root_path / user_header_dot_txt)
        self.selected_profile = self.profile_list[0].name if self.profile_list else None
        return self.session_state()

    def device_disconnect(self) -> dict[str, Any]:
        self.root_path = None
        self.source = None
        self.profile_list = []
        self.selected_profile = None
        self.device = dp_type()
        return _result(ok=True)

    def device_reset(self, reboot_to_msc: bool = False) -> dict[str, Any]:
        if not self.device.info_dict:
            raise CoreError(-32000, "No HID duckyPad is connected")
        try:
            hid_op.duckypad_hid_sw_reset(self.device.info_dict, reboot_into_usb_msc_mode=reboot_to_msc)
        except Exception as exc:
            raise CoreError(-32001, "Could not reset duckyPad", {"detail": str(exc)}) from exc
        return _result(ok=True)

    def session_state(self) -> dict[str, Any]:
        if self.root_path is None:
            return _result(connected=False)
        drive = self._drive_for_device(self.device.info_dict) if self.device.info_dict else None
        info = self.device.info_dict or {}
        return _result(
            connected=True,
            source=self.source,
            model=self.model,
            serial=info.get("serial"),
            fw_version=info.get("fw_version"),
            fw_status=self._firmware_status(info) if info else "unknown",
            drive=drive,
            root_path=str(self.root_path),
            user_header=self.user_header,
            stdlib_available=bool(self.stdlib_lines),
            profiles=[self._profile_summary(profile) for profile in self.profile_list],
            selected_profile=self.selected_profile,
            update=self.update,
        )

    def _get_profile(self, name: str) -> duck_objs.dp_profile:
        self._require_session()
        profile = next((item for item in self.profile_list if item.name == name), None)
        if profile is None:
            raise CoreError(-32002, f"Profile not found: {name}")
        return profile

    def _key_json(self, slot: int, key: duck_objs.dp_key | None) -> dict[str, Any] | None:
        if key is None:
            return None
        return {
            "index": slot,
            "name": key.name or "",
            "name_line2": key.name_line2 or "",
            "script": key.script or "",
            "script_on_release": key.script_on_release or "",
            "color": _colour(key.color),
            "allow_abort": bool(key.allow_abort),
            "dont_repeat": bool(key.dont_repeat),
            "repeat_ms": None,
        }

    def profiles_get(self, name: str) -> dict[str, Any]:
        profile = self._get_profile(name)
        return _result(
            name=profile.name,
            bg_color=_colour(profile.bg_color),
            dim_unused=profile.dim_unused,
            is_landscape=profile.is_landscape,
            upper_re_halfstep=profile.is_upper_re_halfstep,
            lower_re_halfstep=profile.is_lower_re_halfstep,
            keylist=[self._key_json(slot, key) for slot, key in enumerate(profile.keylist)],
        )

    def profiles_update(self, name: str, patch: dict[str, Any]) -> dict[str, Any]:
        profile = self._get_profile(name)
        for field in ("dim_unused", "is_landscape", "upper_re_halfstep", "lower_re_halfstep"):
            if field in patch:
                setattr(profile, field, bool(patch[field]))
        if "bg_color" in patch:
            profile.bg_color = self._validate_colour(patch["bg_color"])
        if "keylist" in patch:
            incoming = patch["keylist"]
            if not isinstance(incoming, list) or len(incoming) != MAX_KEY_COUNT:
                raise CoreError(-32002, f"keylist must contain {MAX_KEY_COUNT} slots")
            profile.keylist = [self._key_from_json(slot, value) for slot, value in enumerate(incoming)]
        if "key" in patch:
            item = patch["key"]
            slot = item.get("index") if isinstance(item, dict) else None
            if not isinstance(slot, int) or not 0 <= slot < MAX_KEY_COUNT:
                raise CoreError(-32002, "key.index must be a valid canonical slot")
            profile.keylist[slot] = self._key_from_json(slot, item)
        return self.session_state()

    def _validate_colour(self, value: Any) -> tuple[int, int, int] | None:
        if value is None:
            return None
        if not isinstance(value, list) or len(value) != 3 or any(not isinstance(item, int) or item < 0 or item > 255 for item in value):
            raise CoreError(-32002, "color must be [r,g,b]")
        return tuple(value)

    def _key_from_json(self, slot: int, value: Any) -> duck_objs.dp_key | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise CoreError(-32002, "key slot must be an object or null")
        key = duck_objs.dp_key()
        key.index = slot + 1
        key.name = str(value.get("name", "")).strip()[:7] or None
        key.name_line2 = str(value.get("name_line2", "")).strip()[:7] or None
        key.script = str(value.get("script", ""))
        key.script_on_release = str(value.get("script_on_release", ""))
        key.color = self._validate_colour(value.get("color"))
        key.allow_abort = bool(value.get("allow_abort", False))
        key.dont_repeat = bool(value.get("dont_repeat", False))
        return key

    def profiles_create(self, name: str) -> dict[str, Any]:
        self._require_session()
        name = self._validate_name(name)
        if any(profile.name == name for profile in self.profile_list):
            raise CoreError(-32002, "Profile name already exists")
        profile = duck_objs.dp_profile()
        profile.name = name
        self.profile_list.append(profile)
        self.selected_profile = name
        return self.session_state()

    def profiles_rename(self, name: str, new_name: str) -> dict[str, Any]:
        profile = self._get_profile(name)
        new_name = self._validate_name(new_name)
        if new_name != name and any(item.name == new_name for item in self.profile_list):
            raise CoreError(-32002, "Profile name already exists")
        profile.name = new_name
        if self.selected_profile == name:
            self.selected_profile = new_name
        return self.session_state()

    def profiles_duplicate(self, name: str) -> dict[str, Any]:
        source = self._get_profile(name)
        base = f"{name} copy"[:MAX_PROFILE_NAME_LEN]
        candidate = base
        number = 2
        while any(item.name == candidate for item in self.profile_list):
            suffix = f" {number}"
            candidate = f"{base[:MAX_PROFILE_NAME_LEN-len(suffix)]}{suffix}"
            number += 1
        copy = duck_objs.dp_profile()
        copy.name = candidate
        copy.bg_color = source.bg_color
        copy.kd_color = source.kd_color
        copy.dim_unused = source.dim_unused
        copy.is_landscape = source.is_landscape
        copy.is_upper_re_halfstep = source.is_upper_re_halfstep
        copy.is_lower_re_halfstep = source.is_lower_re_halfstep
        copy.keylist = [self._key_from_json(slot, self._key_json(slot, key)) for slot, key in enumerate(source.keylist)]
        self.profile_list.insert(self.profile_list.index(source) + 1, copy)
        self.selected_profile = candidate
        return self.session_state()

    def profiles_delete(self, name: str) -> dict[str, Any]:
        profile = self._get_profile(name)
        index = self.profile_list.index(profile)
        self.profile_list.pop(index)
        self.selected_profile = self.profile_list[min(index, len(self.profile_list) - 1)].name if self.profile_list else None
        return self.session_state()

    def profiles_move(self, name: str, direction: str) -> dict[str, Any]:
        profile = self._get_profile(name)
        index = self.profile_list.index(profile)
        delta = -1 if direction == "up" else 1 if direction == "down" else None
        if delta is None:
            raise CoreError(-32002, "direction must be up or down")
        destination = index + delta
        if 0 <= destination < len(self.profile_list):
            self.profile_list[index], self.profile_list[destination] = self.profile_list[destination], self.profile_list[index]
        return self.session_state()

    def profiles_select(self, name: str | None) -> dict[str, Any]:
        if name is not None:
            self._get_profile(name)
        self.selected_profile = name
        return self.session_state()

    def _validate_name(self, value: str) -> str:
        value = str(value).strip()
        if not value or len(value) > MAX_PROFILE_NAME_LEN or any(char in value for char in "\\/:*?\"<>|"):
            raise CoreError(-32002, f"Profile name must be 1-{MAX_PROFILE_NAME_LEN} safe characters")
        return value

    def profiles_save(self, name: str | None = None, to: str = "device") -> dict[str, Any]:
        self._require_session()
        if to not in {"device", "backup"}:
            raise CoreError(-32002, "to must be device or backup")
        if name is not None:
            self._get_profile(name)
        is_hid_device_save = to == "device" and self.source == "device" and self.device.connection_type == self.device.hidmsg
        destination = self.root_path if to == "device" else Path(backup_path) / self._backup_name()
        staging = Path(temp_dir_path) / f"hid-write-{int(time.time() * 1000)}"
        try:
            if is_hid_device_save:
                self._write_all(staging)
                self._sync_dp20(staging)
                self._write_all(self.root_path)
            else:
                self._write_all(destination)
        except CoreError:
            raise
        except Exception as exc:
            raise CoreError(-32004, "Failed to save profiles", {"detail": str(exc)}) from exc
        finally:
            if is_hid_device_save:
                shutil.rmtree(staging, ignore_errors=True)
        return _result(ok=True, saved=[item.name for item in self.profile_list] if name is None else [name], path=str(destination))

    def _backup_name(self) -> str:
        prefix = "duckyPad_Pro_backup_" if self.model == "dp24" else "duckyPad_backup_"
        return prefix + datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    def _write_all(self, destination: Path) -> None:
        compiled = self._compile_profiles()
        if destination.exists():
            for entry in destination.iterdir():
                if entry.is_dir() and entry.name.startswith("profile_"):
                    shutil.rmtree(entry)
                elif entry.name in {profile_info_dot_txt, user_header_dot_txt}:
                    entry.unlink()
        destination.mkdir(parents=True, exist_ok=True)
        (destination / profile_info_dot_txt).write_text("".join(f"{index + 1} {profile.name}\n" for index, profile in enumerate(self.profile_list)), encoding="utf-8")
        if self.user_header:
            (destination / user_header_dot_txt).write_text("".join(f"{line}\n" for line in self.user_header), encoding="utf-8")
        for profile in self.profile_list:
            profile_dir = destination / f"profile_{profile.name}"
            profile_dir.mkdir()
            config: list[str] = []
            for slot, key in enumerate(profile.keylist):
                if key is None:
                    continue
                device_index = self._device_key_index(slot)
                if device_index is None:
                    continue
                config.append(f"z{device_index} {key.name or ''}\n")
                if key.name_line2:
                    config.append(f"x{device_index} {key.name_line2}\n")
                if key.allow_abort:
                    config.append(f"ab {device_index}\n")
                if key.dont_repeat:
                    config.append(f"dr {device_index}\n")
            config.append("BG_COLOR %d %d %d\n" % profile.bg_color)
            if profile.kd_color is not None:
                config.append("KEYDOWN_COLOR %d %d %d\n" % profile.kd_color)
            if not profile.dim_unused:
                config.append("DIM_UNUSED_KEYS 0\n")
            if profile.is_landscape:
                config.append("IS_LANDSCAPE 1\n")
            if profile.is_upper_re_halfstep:
                config.append("UPPER_HS 1\n")
            if profile.is_lower_re_halfstep:
                config.append("LOWER_HS 1\n")
            for slot, key in enumerate(profile.keylist):
                if key is None:
                    continue
                device_index = self._device_key_index(slot)
                if device_index is None:
                    continue
                (profile_dir / f"key{device_index}.txt").write_text(key.script or "", encoding="utf-8", newline="")
                if key.script_on_release:
                    (profile_dir / f"key{device_index}-release.txt").write_text(key.script_on_release, encoding="utf-8", newline="")
                (profile_dir / f"key{device_index}.dsb").write_bytes(compiled[(profile.name, slot, False)])
                if key.script_on_release:
                    (profile_dir / f"key{device_index}-release.dsb").write_bytes(compiled[(profile.name, slot, True)])
                if key.color is not None:
                    config.append("SWCOLOR_%d %d %d %d\n" % (device_index, *key.color))
            (profile_dir / "config.txt").write_text("".join(config), encoding="utf-8", newline="")

    def _device_key_index(self, slot: int) -> int | None:
        return DP20_SLOT_TO_DEVICE.get(slot) if self.model == "dp20" else slot + 1

    def _compile_profiles(self) -> dict[tuple[str, int, bool], bytes]:
        output: dict[tuple[str, int, bool], bytes] = {}
        for profile in self.profile_list:
            for slot, key in enumerate(profile.keylist):
                if key is None:
                    continue
                output[(profile.name, slot, False)] = self._compile(key, key.script or "")
                if key.script_on_release:
                    output[(profile.name, slot, True)] = self._compile(key, key.script_on_release)
        return output

    def _compile(self, key: duck_objs.dp_key, script: str) -> bytes:
        listing = make_final_script(key, script.lstrip(" \t").split("\n"))
        imports = dsvm_preprocessor.preprocess_import_str_dict(self._imports())
        result = dsvm_make_bytecode.make_dsb_no_exception(make_list_of_ds_line_obj_from_str_listing(listing), import_name_to_line_obj_dict=imports)
        if not result.is_success:
            raise CoreError(-32003, result.error_comment, {"line": result.error_line_number_starting_from_1, "message": result.error_comment})
        return bytes(result.bin_array)

    def _sync_dp20(self, temporary_write: Path) -> None:
        assert self.root_path is not None
        try:
            my_compare.duckypad_file_sync(str(self.root_path), str(temporary_write), self.device, None, None)
            hid_op.duckypad_hid_sw_reset(self.device.info_dict)
        except Exception as exc:
            raise CoreError(-32001, "Saved backup but failed to sync duckyPad 2020", {"detail": str(exc)}) from exc

    def profiles_export(self, names: list[str], dir: str) -> dict[str, Any]:
        self._require_session()
        if not names:
            raise CoreError(-32002, "Choose at least one profile to export")
        selected = [self._get_profile(name) for name in names]
        destination = Path(dir)
        if not destination.is_dir():
            raise CoreError(-32004, "Export directory does not exist")
        scratch = Path(temp_dir_path) / f"export-{int(time.time() * 1000)}"
        original = self.profile_list
        try:
            self.profile_list = selected
            self._write_all(scratch)
            zip_path = destination / "duckyPad_Profile.zip"
            zip_directory(str(scratch), str(zip_path))
        finally:
            self.profile_list = original
            shutil.rmtree(scratch, ignore_errors=True)
        return _result(ok=True, path=str(zip_path))

    def profiles_import(self, path: str, model: str) -> dict[str, Any]:
        self._require_session()
        source = Path(path)
        if not source.is_file() or source.suffix.lower() != ".zip":
            raise CoreError(-32002, "Import must be a duckyPad_Profile.zip file")
        staging = Path(temp_dir_path) / f"import-{int(time.time() * 1000)}"
        try:
            unzip_to_own_directory(str(source), str(staging))
            root = next((entry for entry in staging.iterdir() if entry.is_dir()), staging)
            imported = duck_objs.build_profile(str(root))
            if model == "dp20":
                self._convert_dp20_list(imported)
            names = {profile.name for profile in self.profile_list}
            for profile in imported:
                if profile.name not in names:
                    self.profile_list.append(profile)
                    names.add(profile.name)
        except Exception as exc:
            raise CoreError(-32004, "Could not import profile zip", {"detail": str(exc)}) from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return self.session_state()

    def _convert_dp20_list(self, profiles: list[duck_objs.dp_profile]) -> None:
        for profile in profiles:
            converted: list[duck_objs.dp_key | None] = [None] * MAX_KEY_COUNT
            for source_slot, key in enumerate(profile.keylist):
                if key is not None and source_slot < len(DP20_SLOTS):
                    converted[DP20_SLOTS[source_slot]] = key
            profile.keylist = converted

    def _convert_dp20_to_canonical(self) -> None:
        self._convert_dp20_list(self.profile_list)

    def _read_header(self, path: Path) -> list[str]:
        try:
            return [line.rstrip("\r\n") for line in path.read_text(encoding="utf-8").splitlines()]
        except OSError:
            return []

    def headers_get(self) -> dict[str, Any]:
        self._require_session()
        return _result(user_header=self.user_header, stdlib_lines=self.stdlib_lines or None)

    def headers_set(self, user_header: list[str]) -> dict[str, Any]:
        self._require_session()
        if not isinstance(user_header, list) or any(not isinstance(line, str) for line in user_header):
            raise CoreError(-32002, "user_header must be a list of strings")
        self.user_header = user_header
        return self.session_state()

    def headers_fetch_stdlib(self) -> dict[str, Any]:
        try:
            library_path = str(Path(backup_path).parent / "dpds_libs")
            status = ds_stdlib.fetch_update(library_path, force_fetch=True)
            self.stdlib_lines = ds_stdlib.get_latest_stdlib_lines(library_path)
            return _result(ok=True, stdlib_lines=self.stdlib_lines, fetch_status=getattr(status, "name", str(status)))
        except Exception as exc:
            raise CoreError(-32005, "Could not fetch duckyScript stdlib", {"detail": str(exc)}) from exc

    def _imports(self) -> dict[str, list[str]]:
        return {user_header_source_tag_NO_SPACE: self.user_header, stdlib_source_tag_NO_SPACE: self.stdlib_lines}

    def script_check(self, script: str, on_release: int = 0) -> dict[str, Any]:
        if not isinstance(script, str):
            raise CoreError(-32002, "script must be a string")
        key = duck_objs.dp_key()
        key.index = 1
        try:
            binary = self._compile(key, script)
        except CoreError:
            raise
        return _result(ok=True, dsb=base64.b64encode(binary).decode("ascii"))

    def herdr_status(self) -> dict[str, Any]:
        try:
            status = herdr.herdr_status()
            env = _jsonable(status.env)
            config = _jsonable(status.config)
            return _result(env=env, plugin={"installed": None, "version": None, "service_ok": None}, config=config, dfu={"verified": status.herdr_dfu_verified})
        except Exception as exc:
            return _result(env=None, plugin=None, config=None, dfu=None, unavailable=True, detail=str(exc))

    def herdr_install(self) -> dict[str, Any]:
        logs: list[str] = []
        try:
            result = herdr.HerdrIntegration().install(on_progress=lambda text: logs.append(str(text)))
            return _result(ok=bool(getattr(result, "ok", True)), log="\n".join(logs) or str(result))
        except Exception as exc:
            raise CoreError(-32004, "Could not install herdr", {"detail": str(exc), "log": "\n".join(logs)}) from exc

    def herdr_uninstall(self) -> dict[str, Any]:
        try:
            return _result(ok=True, log=str(herdr.HerdrIntegration().uninstall()))
        except Exception as exc:
            raise CoreError(-32004, "Could not uninstall herdr", {"detail": str(exc)}) from exc

    def herdr_flash(self, image: str) -> dict[str, Any]:
        if image not in {"herdr", "stock"}:
            raise CoreError(-32002, "image must be herdr or stock")
        integration = herdr.HerdrIntegration()
        command = integration.firmware_flash_command() if image == "herdr" else integration.stock_flash_command()
        if not command:
            raise CoreError(-32004, "Requested firmware image is not available")
        self.emit("event/herdr/flash", {"phase": "write", "detail": command})
        # The firmware helper intentionally exposes a reviewed shell command. Never invoke a
        # shell string: split it into argv and keep execution visible to the UI.
        import shlex
        import subprocess
        try:
            completed = subprocess.run(shlex.split(command), text=True, capture_output=True, check=True)
        except subprocess.CalledProcessError as exc:
            self.emit("event/herdr/flash", {"phase": "error", "detail": exc.stderr or str(exc)})
            raise CoreError(-32001, "Firmware flash failed", {"detail": exc.stderr or str(exc)}) from exc
        detail = (completed.stdout or "") + (completed.stderr or "")
        self.emit("event/herdr/flash", {"phase": "done", "detail": detail})
        return _result(ok=True, log=detail)

    def update_check(self, include_ts: bool = True) -> dict[str, Any]:
        previous_url = check_update.pc_app_release_url
        try:
            check_update.pc_app_release_url = "https://api.github.com/repos/botio/duckyPad-Configurator/releases/latest"
            app = check_update.get_pc_app_update_status(APP_VERSION)
            firmware = check_update.get_firmware_update_status(self.device.info_dict) if self.device.info_dict else 2
        except Exception:
            app, firmware = 2, 2
        finally:
            check_update.pc_app_release_url = previous_url
        self.update = {"app": app, "app_latest": None, "firmware": firmware, "firmware_latest": None}
        return _result(**self.update) if include_ts else self.update
