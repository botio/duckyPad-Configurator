from __future__ import annotations

import os
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
        import dp20_dumpsd
        original_device = dp20_dumpsd.hid.device

        class _FakeDP20:
            files = {
                "/profile_info.txt": b"0 Default\n",
                "/profile_Default/config.txt": b"z1 Hello\n",
                # UTF-8 spans the first 61-byte boundary; the file spans four reports.
                "/profile_Default/key1.txt": ("STRING " + "a" * 53 + "測試" * 30 + "\n").encode("utf-8"),
                "/profile_Default/key2.txt": b"",
                "/user_header.txt": b"// " + b"h" * 58,
            }

            def __init__(self, fail_path=None, break_after_failure=False):
                self.paths = []
                self.commands = []
                self.current_path = None
                self.offset = 0
                self.fail_path = fail_path
                self.break_after_failure = break_after_failure
                self.broken = False
                self.read_timeouts = []

            def open_path(self, path):
                self.paths.append(path)

            def write(self, packet):
                if self.broken:
                    raise OSError("stale HID handle")
                command = packet[2]
                self.commands.append(command)
                if command == dp20_dumpsd.HID_COMMAND_OPEN_FILE_FOR_READING:
                    self.current_path = bytes(packet[3:]).split(b"\0", 1)[0].decode()
                    self.offset = 0

            def read(self, _size, timeout_ms=None):
                self.read_timeouts.append(timeout_ms)
                if self.commands[-1] == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS:
                    return [4, 0, 0] + [0] * 61
                if self.commands[-1] == dp20_dumpsd.HID_COMMAND_OPEN_FILE_FOR_READING:
                    if self.current_path == self.fail_path:
                        self.broken = self.break_after_failure
                        raise OSError("forced file read failure")
                    status = 0 if self.current_path in self.files else 4
                    return [4, 0, status] + [0] * 61
                content = self.files[self.current_path]
                chunk = content[self.offset:self.offset + 61]
                self.offset += len(chunk)
                return [4, 0, len(chunk)] + list(chunk) + [0] * (61 - len(chunk))

            def close(self):
                pass

        fake_dp20 = _FakeDP20()
        try:
            dp20_dumpsd.hid.device = lambda: fake_dp20
            dp20_dump = root / "dp20-dump"
            check(
                dp20_dumpsd.dump_sd(b"/dev/mock-duckypad", str(dp20_dump), str(root / "backup")),
                "dp20 direct file mirror completes",
            )
            check(
                fake_dp20.commands[-1] == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS
                and all(
                    (dp20_dump / path.lstrip("/")).read_bytes() == content
                    for path, content in fake_dp20.files.items()
                ),
                "dp20 mirrors files before safely exiting File Access Mode",
            )
            check(
                fake_dp20.read_timeouts
                and all(
                    timeout is not None and timeout <= 2000
                    for timeout in fake_dp20.read_timeouts
                ),
                "dp20 bounds every HID response wait below the connect timeout",
            )

            class _OversizedChunkDP20(_FakeDP20):
                def read(self, size, timeout_ms=None):
                    if self.commands[-1] == dp20_dumpsd.HID_COMMAND_READ_FILE:
                        return [4, 0, 62] + [0] * 61
                    return super().read(size, timeout_ms)

            try:
                dp20_dumpsd.hid_dump_file("/profile_info.txt", _OversizedChunkDP20())
            except OSError:
                pass
            else:
                raise AssertionError("dp20 accepted a chunk exceeding report capacity")
            print("PASS dp20 rejects a 62-byte chunk in a 64-byte report")
            transient_dp20 = _FakeDP20("/profile_Default/config.txt")
            retry_dp20 = _FakeDP20()
            retry_devices = iter((transient_dp20, retry_dp20))
            dp20_dumpsd.hid.device = lambda: next(retry_devices)
            transient_dump = root / "transient-dp20-dump"
            check(
                dp20_dumpsd.dump_sd(
                    b"/dev/mock-duckypad", str(transient_dump), str(root / "backup")
                ),
                "dp20 retries the complete mirror after a transient HID failure",
            )
            check(
                transient_dp20.commands[-1]
                == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS
                and retry_dp20.commands[-1]
                == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS,
                "dp20 exits File Access Mode between complete mirror attempts",
            )
            failing_dp20 = _FakeDP20("/profile_Default/config.txt")
            dp20_dumpsd.hid.device = lambda: failing_dp20
            failed_dump = root / "failed-dp20-dump"
            try:
                dp20_dumpsd.dump_sd(
                    b"/dev/mock-duckypad", str(failed_dump), str(root / "backup")
                )
                persistent_error = None
            except OSError as exc:
                persistent_error = exc
            check(
                persistent_error is not None
                and "forced file read failure" in str(persistent_error),
                "dp20 reports the final storage error after bounded retries",
            )
            check(
                failing_dp20.commands[-1] == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS,
                "dp20 exits File Access Mode after a failed mirror",
            )
            broken_dp20 = _FakeDP20(
                "/profile_Default/config.txt", break_after_failure=True
            )
            recovery_dp20 = _FakeDP20()
            recovered_dp20 = _FakeDP20()
            recovery_devices = iter((broken_dp20, recovery_dp20, recovered_dp20))
            dp20_dumpsd.hid.device = lambda: next(recovery_devices)
            retry_dump = root / "retry-dp20-dump"
            check(
                dp20_dumpsd.dump_sd(
                    b"/dev/mock-duckypad", str(retry_dump), str(root / "backup")
                ),
                "dp20 retries the mirror after replacing a stale HID handle",
            )
            check(
                recovery_dp20.commands
                and recovery_dp20.commands[-1]
                == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS,
                "dp20 reopens HID to exit File Access Mode",
            )
        finally:
            dp20_dumpsd.hid.device = original_device
        original_scan = service_module.hid_op.scan_duckypads
        original_drive = service_module.hid_op.get_duckypad_drive
        original_dump = dp20_dumpsd.dump_sd
        original_backup = service_module.backup_path
        scanned_info = {
            "fw_version": "3.1.8",
            "dp_model": 20,
            "serial": "01020304",
            "hid_path": b"/dev/mock-duckypad",
            "hid_msg": [4, 0, 0, 3, 1, 8, 20, 1, 2, 3, 4] + [0] * 53,
        }
        try:
            service_module.hid_op.get_duckypad_path = lambda: [b"/dev/mock-duckypad"]
            service_module.hid_op.probe_duckypad_paths = lambda _paths: ([scanned_info], [])
            service_module.hid_op.get_duckypad_drive = lambda _label: None
            connect_service = CoreService()
            scan = connect_service.device_scan()
            check(scan["devices"][0]["id"] == "01020304", "scan identifies v3.1.8 device")
            service_module.hid_op.scan_duckypads = lambda: []
            service_module.backup_path = str(root / "connect-backup")

            if os.name == "posix" and os.geteuid() != 0:
                locked_dump = root / "hid_dump"
                locked_dump.mkdir()
                locked_toc = locked_dump / "profile_info.txt"
                locked_toc.write_bytes(b"old cached profiles\n")
                locked_toc.chmod(0o444)
                locked_dump.chmod(0o555)
                dp20_dumpsd.hid.device = _FakeDP20
                try:
                    connected = connect_service.device_connect("01020304")
                    mirror = Path(connected["root_path"])
                    check(
                        connected["connected"]
                        and connected["profiles"][0]["name"] == "Default"
                        and all(
                            (mirror / path.lstrip("/")).read_bytes() == content
                            for path, content in _FakeDP20.files.items()
                        ),
                        "connect mirrors real packets despite an unwritable legacy cache",
                    )
                    check(
                        locked_toc.read_bytes() == b"old cached profiles\n"
                        and locked_dump.stat().st_mode & 0o777 == 0o555,
                        "connect preserves legacy cache contents and permissions",
                    )
                    original_temporary_directory = tempfile.TemporaryDirectory
                    attempted_mirrors = []

                    def tracked_mirror(*args, **kwargs):
                        directory = original_temporary_directory(*args, **kwargs)
                        attempted_mirrors.append(Path(directory.name))
                        return directory

                    class _BlockedLocalWriteDP20(_FakeDP20):
                        def read(self, size, timeout_ms=None):
                            response = super().read(size, timeout_ms)
                            if (
                                self.commands[-1] == dp20_dumpsd.HID_COMMAND_READ_FILE
                                and self.current_path == "/profile_info.txt"
                                and response[2] == 0
                            ):
                                blocked = attempted_mirrors[-1] / "profiles"
                                blocked.mkdir()
                                blocked.chmod(0o555)
                            return response

                    blocked_device = _BlockedLocalWriteDP20()
                    dp20_dumpsd.hid.device = lambda: blocked_device
                    tempfile.TemporaryDirectory = tracked_mirror
                    try:
                        try:
                            connect_service.device_connect("01020304")
                        except CoreError as exc:
                            check(
                                exc.code == -32004 and exc.data["stage"] == "local_cache",
                                "local disk failure is not reported as a device read failure",
                            )
                        else:
                            raise AssertionError("connect accepted an unwritable mirror")
                    finally:
                        tempfile.TemporaryDirectory = original_temporary_directory
                        dp20_dumpsd.hid.device = _FakeDP20
                    check(
                        len(blocked_device.paths) == 1
                        and blocked_device.commands[-1] == dp20_dumpsd.HID_COMMAND_EXIT_FILE_ACCESS
                        and not attempted_mirrors[-1].exists()
                        and connect_service.session_state()["root_path"] == str(mirror)
                        and (mirror / "profile_info.txt").read_bytes() == _FakeDP20.files["/profile_info.txt"],
                        "local write failure exits HID without retry, removes partial data, and preserves the active session",
                    )
                    reconnected = connect_service.device_connect("01020304")
                    check(
                        not mirror.exists() and reconnected["connected"],
                        "reconnecting replaces and releases the previous session mirror",
                    )
                    mirror = Path(reconnected["root_path"])
                    second_service = CoreService()
                    second_service.device_scan()
                    second = second_service.device_connect("01020304")
                    second_mirror = Path(second["root_path"])
                    second_service.device_disconnect()
                    check(
                        not second_mirror.exists() and mirror.exists(),
                        "disconnect removes only its own session mirror",
                    )
                    connect_service.device_connect_folder(str(root), "dp20")
                    check(
                        not mirror.exists() and (profile / "config.txt").exists(),
                        "switching to a folder releases the mirror without deleting user files",
                    )
                finally:
                    locked_dump.chmod(0o755)
                    locked_toc.chmod(0o644)
                    dp20_dumpsd.hid.device = original_device
                connect_service.device_scan()

            def fake_dump(_path, dump_dir, _backup, *_ui):
                dump_root = Path(dump_dir)
                profile_dir = dump_root / "profile_Default"
                profile_dir.mkdir(parents=True)
                (dump_root / "profile_info.txt").write_text("0 Default\n")
                (profile_dir / "config.txt").write_text("z1 Hello\n")
                return True

            dp20_dumpsd.dump_sd = fake_dump
            connected = connect_service.device_connect("01020304")
            check(
                connected["connected"] and connected["fw_version"] == "3.1.8",
                "connect uses the device selected by the preceding scan",
            )
            error_service = CoreService()
            error_service.device_scan()

            def failed_dump(*_args):
                raise OSError("HID open file for read failed: 4")

            dp20_dumpsd.dump_sd = failed_dump
            try:
                error_service.device_connect("01020304")
                storage_error = None
            except CoreError as exc:
                storage_error = exc
            check(
                storage_error is not None
                and storage_error.data["detail"]
                == "HID open file for read failed: 4",
                "connect surfaces the final profile storage failure",
            )
        finally:
            service_module.hid_op.get_duckypad_path = original_paths
            service_module.hid_op.probe_duckypad_paths = original_probe
            service_module.hid_op.scan_duckypads = original_scan
            service_module.hid_op.get_duckypad_drive = original_drive
            service_module.backup_path = original_backup
            dp20_dumpsd.dump_sd = original_dump
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
        sidecar = subprocess.run(
            [sys.executable, str(ROOT / "core" / "sidecar.py")],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "hello", "params": {}}) + "\n",
            capture_output=True,
            text=True,
            timeout=15,
            env={
                **os.environ,
                "HOME": temporary,
                "XDG_DATA_HOME": temporary,
                "APPDATA": temporary,
                "LOCALAPPDATA": temporary,
            },
        )
        check(sidecar.returncode == 0, f"sidecar exits cleanly: {sidecar.stderr if sidecar.returncode else ''}")
        response = json.loads(sidecar.stdout)
        check(
            response["jsonrpc"] == "2.0" and response["id"] == 1
            and "result" in response and "error" not in response,
            "fresh-install stdout contains only the correlated JSON-RPC response",
        )

if __name__ == "__main__":
    main()
