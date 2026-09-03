from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core.service as service_module
from core.service import CoreError, CoreService


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "duckypad"
        profile = root / "profile_Alpha"
        profile.mkdir(parents=True)
        (profile / "config.txt").write_text("z1 HELLO\nx1 WORLD\nBG_COLOR 244 241 233\n", encoding="utf-8")
        (profile / "key1.txt").write_text("", encoding="utf-8")
        (root / "profile_info.txt").write_text("1 Alpha\n", encoding="utf-8")
        (root / "user_header.txt").write_text("// header\n", encoding="utf-8")
        service = CoreService()
        state = service.device_connect_folder(str(root), "dp20")
        check(state["connected"] and state["profiles"][0]["name"] == "Alpha", "connect folder")
        loaded = service.profiles_get("Alpha")
        check(loaded["keylist"][0]["name"] == "HELLO", "canonical dp20 key mapping")
        loaded["keylist"][0]["script"] = ""
        service.profiles_update("Alpha", {"keylist": loaded["keylist"]})
        check(service.script_check("")["ok"], "valid script compiles")
        try:
            service.script_check("print 'bad'")
        except CoreError as error:
            check(error.code == -32003, "invalid script reports compiler error")
        else:
            raise AssertionError("invalid script unexpectedly compiled")
        service.profiles_create("Beta")
        service.profiles_rename("Beta", "Gamma")
        service.profiles_move("Gamma", "up")
        service.profiles_duplicate("Gamma")
        service.profiles_delete("Gamma copy")
        check(len(service.session_state()["profiles"]) == 2, "profile CRUD")
        backup = service.profiles_save(to="backup")
        check(Path(backup["path"]).is_dir(), "backup written")
        export = service.profiles_export(["Alpha"], temporary)
        check(Path(export["path"]).is_file(), "zip exported")
        service.headers_set(["// updated"])
        check(service.headers_get()["user_header"] == ["// updated"], "headers persisted in session")
        status = service.herdr_status()
        check("ts" in status, "herdr status is non-fatal without device")
        original_paths = service_module.hid_op.get_duckypad_path
        original_probe = service_module.hid_op.probe_duckypad_paths
        try:
            service_module.hid_op.get_duckypad_path = lambda: [b"/dev/mock-duckypad"]
            service_module.hid_op.probe_duckypad_paths = lambda _paths: ([], ["OSError: access denied"])
            scan = CoreService().device_scan()
            check(scan["compatible_hid_paths"] == 1 and scan["detail"] == "OSError: access denied", "scan reports HID probe failure")
        finally:
            service_module.hid_op.get_duckypad_path = original_paths
            service_module.hid_op.probe_duckypad_paths = original_probe
        import hid_common
        original_hid_module = hid_common.hid
        original_hidapi_error = hid_common._hidapi_global_error
        try:
            class _FakeHidDevice:
                def open_path(self, _path):
                    raise OSError("open failed")
                def close(self):
                    pass
            class _FakeHidModule:
                @staticmethod
                def device():
                    return _FakeHidDevice()
            hid_common.hid = _FakeHidModule
            hid_common._hidapi_global_error = lambda: "hid_open_path: failed to open IOHIDDevice from mach entry: (0xe00002c6) Request denied by service policy"
            _found, _errors = hid_common.probe_duckypad_paths([b"/dev/mock-duckypad"])
            check(_errors and "0xe00002c6" in _errors[0] and "hidapi:" in _errors[0], "hid probe surfaces hidapi IOKit detail")
        finally:
            hid_common.hid = original_hid_module
            hid_common._hidapi_global_error = original_hidapi_error
        _dev = hid_common.hid.device()
        try:
            _dev.open_path(b"/dev/no-such-duckypad-xyz")
        except Exception:
            pass
        finally:
            try:
                _dev.close()
            except Exception:
                pass
        _got = hid_common._hidapi_global_error()
        if sys.platform.startswith("linux"):
            check(_got is None, "real hidapi global-error reader filters the Linux placeholder")
        else:
            check(_got is None or isinstance(_got, str), "real hidapi global-error reader is safe")
        _listen = hid_common._ensure_hid_listen_access()
        if sys.platform.startswith("linux"):
            check(_listen is None, "hid listen-access request is a no-op off macOS")
        else:
            check(_listen is None or isinstance(_listen, bool), "hid listen-access request is safe")
        sidecar = subprocess.Popen([sys.executable, str(ROOT / "core" / "sidecar.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert sidecar.stdin and sidecar.stdout
        sidecar.stdin.write(json.dumps({"jsonrpc":"2.0","id":1,"method":"hello","params":{}}) + "\n")
        sidecar.stdin.flush()
        response = json.loads(sidecar.stdout.readline())
        check(response["result"]["sidecar_version"] == "5.0.9", "NDJSON hello")
        sidecar.terminate(); sidecar.wait(timeout=5)


if __name__ == "__main__":
    main()
