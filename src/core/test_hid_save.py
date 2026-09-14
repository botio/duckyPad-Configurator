"""SAVE contracts exercised through the real service, planner, compiler and HID writer."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core.service as service_module
from core.service import CoreError, CoreService
import hid_common
import hid_op
import my_compare
from hid_common import dp_type
from shared import (
    HID_COMMAND_CLOSE_FILE, HID_COMMAND_CREATE_DIR, HID_COMMAND_DELETE_DIR,
    HID_COMMAND_DELETE_FILE, HID_COMMAND_EXIT_FILE_ACCESS,
    HID_COMMAND_OPEN_FILE_FOR_WRITING, HID_COMMAND_SW_RESET, HID_COMMAND_WRITE_FILE,
)


class SaveDevice:
    def __init__(self, fault=None, unsolicited=False, slow_delete_ms=None,
                 fault_command=HID_COMMAND_WRITE_FILE, fresult=0):
        self.fault = fault
        self.fault_command = fault_command
        self.fresult = fresult
        self.unsolicited = unsolicited
        self.slow_delete_ms = slow_delete_ms
        self.commands = []
        self.files = {}
        self.current = None
        self.access = False
        self.closed = False
        self.replies = []
        self.now = 0.0

    def monotonic(self):
        return self.now

    def open_path(self, _path):
        self.closed = False

    def close(self):
        self.closed = True

    def write(self, packet):
        command = packet[2]
        self.commands.append(command)
        fault = self.fault if command == self.fault_command else None
        response = [4, 0, 0] + [0] * 61
        if command == HID_COMMAND_OPEN_FILE_FOR_WRITING:
            self.access = True
            self.current = bytes(packet[3:]).split(b'\0', 1)[0].decode()
            self.files[self.current] = b''
        elif command == HID_COMMAND_WRITE_FILE:
            # A lost or malformed ACK can occur after a write committed.
            if fault not in ('busy', 'error'):
                self.files[self.current] += bytes(packet[3:3 + packet[1]])
        elif command in (HID_COMMAND_EXIT_FILE_ACCESS, HID_COMMAND_SW_RESET):
            self.access = False
            self.current = None
        elif command == HID_COMMAND_CLOSE_FILE:
            self.current = None
        elif command in (HID_COMMAND_CREATE_DIR, HID_COMMAND_DELETE_DIR, HID_COMMAND_DELETE_FILE):
            self.access = True
        if fault == 'busy':
            response[2] = 2
        elif fault == 'error':
            response[2:4] = [1, self.fresult]
        elif fault == 'invalid_report':
            response[0] = 5
        elif fault == 'invalid_ack':
            response[1] = 1
        elif fault == 'short':
            response = response[:3]
        delay = 0
        if command == HID_COMMAND_DELETE_DIR and self.slow_delete_ms is not None:
            delay = self.slow_delete_ms / 1000.0
            self.slow_delete_ms = None
        self.replies = []
        if self.unsolicited:
            self.replies.append((self.now, [4, 0xF1, 0] + [0] * 61))
        if fault != 'missing':
            self.replies.append((self.now + delay, response))
        return len(packet)

    def read(self, _size, timeout_ms=None):
        if timeout_ms is None:
            raise AssertionError('SAVE performed an unbounded HID read')
        deadline = self.now + timeout_ms / 1000.0
        if not self.replies or self.replies[0][0] > deadline:
            self.now = deadline
            return []
        ready, response = self.replies.pop(0)
        self.now = max(self.now, ready)
        return response


def save_info():
    return {'hid_path': b'save-fixture', 'serial': 'TEST', 'dp_model': 20, 'fw_version': '3.1.16'}


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def check_service_recovery(root):
    mirror = root / 'mirror'
    profile = mirror / 'profile_autohotkey'
    profile.mkdir(parents=True)
    (profile / 'config.txt').write_text('z1 OLD\n', encoding='utf-8')
    (profile / 'key1.txt').write_text('STRING old', encoding='utf-8')
    (mirror / 'profile_info.txt').write_text('1 autohotkey\n', encoding='utf-8')
    events = []
    service = CoreService(emit=lambda name, params: events.append((name, params)))
    service.device_connect_folder(str(mirror), 'dp20')
    service.source = 'device'
    service.device.connection_type = service.device.hidmsg
    service.device.info_dict = save_info()
    service.profiles_rename('autohotkey', 'Fresh')
    service.profiles_update('Fresh', {'key': {'index': 0, 'name': 'EDITED', 'script': 'STRING recovered'}})
    old_mirror = snapshot(mirror)
    backups = root / 'backups'
    saved_backups = []
    with patch.object(service_module, 'backup_path', str(backups)):
        for result in (3, 0):
            events.clear()
            transport = SaveDevice(fault='error', fault_command=HID_COMMAND_DELETE_DIR, fresult=result)
            with patch.object(hid_op.hid, 'device', return_value=transport), patch.object(hid_common.time, 'monotonic', transport.monotonic):
                try:
                    service.profiles_save()
                except CoreError as error:
                    assert error.code == -32001
                    detail = error.data['detail']
                    assert 'DELETE_DIR /profile_autohotkey' in detail and 'status 1' in detail
                    assert 'device firmware 3.1.16' in detail and error.data.get('fw_version') == '3.1.16'
                    if result:
                        assert 'FR_NOT_READY (3)' in detail, 'raw FatFs cause did not reach the service consumer'
                    else:
                        assert 'FR_NOT_READY' not in detail, 'legacy status 1 guessed a filesystem cause'
                    backup = Path(error.data['backup_path'])
                    assert (error.message + "\n" + detail).count(str(backup)) == 1
                else:
                    raise AssertionError('service reported success after failed DELETE_DIR')
            assert backup.parent == backups and backup.is_dir(), 'reported recovery backup is not persistent'
            assert backup not in saved_backups, 'repeated SAVE overwrote its previous recovery backup'
            saved_backups.append(backup)
            assert snapshot(mirror) == old_mirror, 'failed sync changed the comparison mirror'
            assert service.profiles_get('Fresh')['keylist'][0]['script'] == 'STRING recovered', 'failed sync lost in-memory edits'
            recovered = CoreService()
            recovered.device_connect_folder(str(backup), 'dp20')
            key = recovered.profiles_get('Fresh')['keylist'][0]
            assert key['script'] == 'STRING recovered' and key['name'] == 'EDITED', 'saved backup cannot recover edited profiles'
            assert ('event/profiles/save', {'phase': 'transfer', 'path': 'profile_autohotkey'}) in events, 'SAVE progress never reaches the subscribed event channel'
            assert transport.commands.count(HID_COMMAND_DELETE_DIR) == 1, 'failed delete was replayed'
            assert HID_COMMAND_SW_RESET not in transport.commands, 'failed sync reset the device'
            assert not transport.access and transport.closed, 'failed SAVE left File Access Mode active'
        assert snapshot(saved_backups[0]) == snapshot(saved_backups[1]), 'retry damaged the earlier backup'
        print('PASS failed service SAVE retains compiled recovery data, edits, mirror and precise filesystem diagnostics')

        # The retained artifact is the exact source of the successful HID write,
        # including bytecode; the apply reset still runs after all ACKs succeed.
        transport = SaveDevice(unsolicited=True)
        with patch.object(hid_op.hid, 'device', return_value=transport), patch.object(hid_op, 'scan_duckypads', return_value=[save_info()]), patch.object(hid_common.time, 'monotonic', transport.monotonic):
            service.profiles_save()
        compiled_backup = snapshot(saved_backups[0])
        assert 'profile_Fresh/key1.dsb' in compiled_backup, 'recovery backup omitted compiled key data'
        assert snapshot(mirror) == compiled_backup, 'successful SAVE did not advance the mirror to the compiled backup'
        assert transport.files == {'/' + path: data for path, data in compiled_backup.items()}, 'HID SAVE did not transfer the exact compiled recovery data'
        assert transport.commands[-1] == HID_COMMAND_SW_RESET and not transport.access and transport.closed
        print('PASS successful service SAVE writes compiled backup bytes and resets to apply them')

        before = {path: snapshot(path) for path in backups.iterdir()}
        old_mirror = snapshot(mirror)
        service.profiles_update('Fresh', {'key': {'index': 0, 'script': 'PRINT hello'}})
        transport = SaveDevice()
        with patch.object(hid_op.hid, 'device', return_value=transport):
            try:
                service.profiles_save()
            except CoreError as error:
                assert error.code == -32003 and error.data['profile'] == 'Fresh' and error.data['key'] == 1
                assert 'backup_path' not in error.data, 'compilation failure claimed a completed backup'
            else:
                raise AssertionError('invalid script compiled during HID SAVE')
        assert {path: snapshot(path) for path in backups.iterdir()} == before, 'compilation failure left an incomplete backup or damaged an earlier one'
        assert snapshot(mirror) == old_mirror and not transport.commands, 'compilation failure touched mirror or hardware'
        assert service.profiles_get('Fresh')['keylist'][0]['script'] == 'PRINT hello'
        print('PASS compilation failure preserves edits without advertising or leaving an incomplete backup')


def run_checks():
    with tempfile.TemporaryDirectory() as temporary:
        original = Path(temporary) / 'original'
        modified = Path(temporary) / 'modified'
        original.mkdir()
        modified.mkdir()
        content = b'1 Default\n' * 25  # several independently acknowledged chunks
        (modified / 'profile_info.txt').write_bytes(content)
        device = dp_type()
        device.connection_type = device.hidmsg
        device.device_type = device.dp20
        device.info_dict = save_info()
        for fault in ('missing', 'busy', 'error', 'invalid_report', 'invalid_ack', 'short'):
            transport = SaveDevice(fault=fault)
            with patch.object(hid_op.hid, 'device', return_value=transport), patch.object(hid_common.time, 'monotonic', transport.monotonic):
                try:
                    my_compare.duckypad_file_sync(str(original), str(modified), device)
                except OSError:
                    pass
                else:
                    raise AssertionError(f'SAVE reported success after {fault} WRITE acknowledgement')
            assert not transport.access and transport.closed, f'{fault} leaves device in File Access Mode'
            assert transport.commands.count(HID_COMMAND_WRITE_FILE) == 1, 'uncertain write was replayed or transfer continued'
            if fault == 'missing':
                assert 0 < transport.now < 2, 'lost write ACK did not fail within the chunk deadline'
            print(f'PASS SAVE {fault} ACK stops transfer and exits File Access Mode')
        transport = SaveDevice(unsolicited=True)
        with patch.object(hid_op.hid, 'device', return_value=transport), patch.object(hid_common.time, 'monotonic', transport.monotonic):
            my_compare.duckypad_file_sync(str(original), str(modified), device)
        assert transport.files['/profile_info.txt'] == content, 'SAVE corrupts chunked content'
        assert transport.closed, 'successful SAVE leaks its HID handle'
        print('PASS SAVE writes exact multi-chunk content despite Herdr reports and releases its handle')

        # The virtual HID read respects its deadline: unlike sleeping and then
        # returning an ACK, a two-second response fails at a 1.5-second bound.
        (original / 'profile_Old').mkdir()
        (original / 'profile_Old' / 'config.txt').write_bytes(b'z1 Old\n')
        for delay_ms, completes in ((2000, True), (31000, False)):
            transport = SaveDevice(slow_delete_ms=delay_ms, unsolicited=True)
            with patch.object(hid_op.hid, 'device', return_value=transport), patch.object(hid_common.time, 'monotonic', transport.monotonic):
                try:
                    my_compare.duckypad_file_sync(str(original), str(modified), device)
                except OSError as error:
                    assert not completes and 'DELETE_DIR timed out' in str(error)
                else:
                    assert completes, 'SAVE waited beyond the recursive-delete deadline'
            assert transport.commands.count(HID_COMMAND_DELETE_DIR) == 1, 'timed-out delete was replayed'
            if completes:
                assert transport.files['/profile_info.txt'] == content
                assert transport.now == 2, 'slow delete ACK was not actually awaited'
            else:
                assert 29 <= transport.now <= 30 and not transport.access, 'delete timeout did not terminate boundedly'
            assert transport.closed, 'slow-delete SAVE leaks its HID handle'
        print('PASS SAVE accepts a two-second delete and terminates an over-deadline delete without replay')
        check_service_recovery(Path(temporary))


if __name__ == '__main__':
    run_checks()
