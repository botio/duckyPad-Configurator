"""SAVE contracts exercised through the real planner and HID writer."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hid_op
import my_compare
from hid_common import dp_type
from shared import (
    HID_COMMAND_CLOSE_FILE, HID_COMMAND_CREATE_DIR, HID_COMMAND_DELETE_DIR,
    HID_COMMAND_DELETE_FILE, HID_COMMAND_EXIT_FILE_ACCESS,
    HID_COMMAND_OPEN_FILE_FOR_WRITING, HID_COMMAND_SW_RESET, HID_COMMAND_WRITE_FILE,
)


class SaveDevice:
    def __init__(self, fault=None, unsolicited=False, slow_delete_ms=None):
        self.fault = fault
        self.unsolicited = unsolicited
        self.slow_delete_ms = slow_delete_ms
        self.commands = []
        self.files = {}
        self.current = None
        self.access = False
        self.closed = False
        self.replies = []
        self.read_timeouts = []

    def open_path(self, _path):
        self.closed = False

    def close(self):
        self.closed = True

    def write(self, packet):
        command = packet[2]
        self.commands.append(command)
        response = [4, 0, 0] + [0] * 61
        if command == HID_COMMAND_OPEN_FILE_FOR_WRITING:
            self.access = True
            self.current = bytes(packet[3:]).split(b'\0', 1)[0].decode()
            self.files[self.current] = b''
        elif command == HID_COMMAND_WRITE_FILE:
            # A lost acknowledgement can occur after the write committed.
            if self.fault not in ('busy', 'error'):
                self.files[self.current] += bytes(packet[3:3 + packet[1]])
            if self.fault == 'missing':
                self.replies = [[]]
                return len(packet)
            if self.fault == 'busy':
                response[2] = 2
            if self.fault == 'error':
                response[2] = 1
        elif command in (HID_COMMAND_EXIT_FILE_ACCESS, HID_COMMAND_SW_RESET):
            self.access = False
            self.current = None
        elif command == HID_COMMAND_CLOSE_FILE:
            self.current = None
        elif command in (HID_COMMAND_CREATE_DIR, HID_COMMAND_DELETE_DIR, HID_COMMAND_DELETE_FILE):
            self.access = True
        self.replies = ([[4, 0xF1, 0] + [0] * 61] if self.unsolicited else []) + [response]
        return len(packet)

    def read(self, _size, timeout_ms=None):
        self.read_timeouts.append(timeout_ms)
        if self.slow_delete_ms is not None and self.commands and self.commands[-1] == HID_COMMAND_DELETE_DIR:
            sleep = self.slow_delete_ms
            self.slow_delete_ms = None  # slow only the first delete
            if sleep:
                time.sleep(sleep / 1000.0)
        return self.replies.pop(0) if self.replies else []


def save_info():
    return {'hid_path': b'save-fixture', 'serial': 'TEST', 'dp_model': 20, 'fw_version': '3.1.16'}


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
        for fault in ('missing', 'busy', 'error'):
            transport = SaveDevice(fault=fault)
            with patch.object(hid_op.hid, 'device', return_value=transport):
                try:
                    my_compare.duckypad_file_sync(str(original), str(modified), device)
                except OSError:
                    pass
                else:
                    raise AssertionError(f'SAVE reported success after {fault} WRITE acknowledgement')
            assert not transport.access and transport.closed, f'{fault} leaves device in File Access Mode'
            assert transport.commands.count(HID_COMMAND_WRITE_FILE) == 1, 'uncertain write was replayed or transfer continued'
            assert all(timeout is not None and 0 < timeout < 30000 for timeout in transport.read_timeouts), 'SAVE can outlive RPC while waiting for one reply'
            print(f'PASS SAVE {fault} ACK stops transfer and exits File Access Mode')
        transport = SaveDevice(unsolicited=True)
        with patch.object(hid_op.hid, 'device', return_value=transport):
            my_compare.duckypad_file_sync(str(original), str(modified), device)
        assert transport.files['/profile_info.txt'] == content, 'SAVE corrupts chunked content'
        # The sync leaves File Access Mode for the subsequent SW_RESET apply step
        # (see _sync_dp20); only the handle must be released here.
        assert transport.closed, 'successful SAVE leaks its HID handle'
        print('PASS SAVE writes exact multi-chunk content despite Herdr reports and releases its handle')

        # A recursive profile delete blocks the pad over SPI for several seconds;
        # it must not be mistaken for a lost acknowledgement at the fast bound.
        original = Path(temporary) / 'original2'
        modified = Path(temporary) / 'modified2'
        original.mkdir()
        modified.mkdir()
        (original / 'profile_Old').mkdir()
        (original / 'profile_Old' / 'config.txt').write_bytes(b'z1 Old\n')
        (modified / 'profile_info.txt').write_bytes(b'1 Fresh\n')
        transport = SaveDevice(slow_delete_ms=2000)
        with patch.object(hid_op.hid, 'device', return_value=transport):
            my_compare.duckypad_file_sync(str(original), str(modified), device)
        assert HID_COMMAND_DELETE_DIR in transport.commands, 'removed profile did not generate DELETE_DIR'
        delete_reads = [
            timeout for command, timeout in zip(transport.commands, transport.read_timeouts)
            if command == HID_COMMAND_DELETE_DIR
        ]
        assert all(timeout is not None and timeout >= 2000 for timeout in delete_reads), 'DELETE_DIR is bounded by the fast chunk ceiling'
        assert transport.closed, 'slow-delete SAVE leaks its HID handle'
        print('PASS SAVE waits out a slow directory delete instead of timing out at the chunk bound')


if __name__ == '__main__':
    run_checks()
