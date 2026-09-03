import ctypes
import hid
import os
import sys
from datetime import datetime, timezone

_HIDAPI_LIB = None

def _hidapi_global_error():
    """Return the last global error recorded by libhidapi, or None.

    hidapi records a global error string when calls such as hid_open_path()
    fail (on macOS this carries the IOKit code/message, e.g. kIOReturnDenied),
    but the Python binding never reads it. The trezor/cython-hidapi wheel
    statically compiles the hidapi C code into the ``hid`` extension module
    itself (there is no separate ``hidapi.so``), so we dlopen that module's
    own file and call ``hid_error(NULL)`` to retrieve the string.
    """
    global _HIDAPI_LIB
    try:
        if _HIDAPI_LIB is None:
            _HIDAPI_LIB = ctypes.CDLL(os.path.abspath(hid.__file__))
        hid_error = _HIDAPI_LIB.hid_error
        # hid_error returns a const wchar_t* on every platform.
        hid_error.restype = ctypes.c_wchar_p
        hid_error.argtypes = [ctypes.c_void_p]
        result = hid_error(None)
    except Exception:
        return None
    if result is None:
        return None
    if isinstance(result, bytes):
        result = result.decode('utf-8', 'replace')
    # These placeholders carry no diagnostic value (the Linux backend does not
    # implement hid_error; a clean state reports "Success").
    if not result or result in ('Success', 'hid_error is not implemented yet'):
        return None
    return result


def _ensure_hid_listen_access():
    """On macOS, request TCC "Input Monitoring" (ListenEvent) access.

    Opening a keyboard-class HID device (the duckyPad) is gated by the
    Input Monitoring privacy permission. Declaring
    NSInputMonitoringUsageDescription lets macOS recognize the intent, but
    the app should also actively register for it via IOHIDRequestAccess()
    so the system can prompt for and track the grant. Returns True if
    access is already permitted, False if it still needs to be granted,
    or None if the call was unavailable. Never fatal: if this fails the
    subsequent open simply fails with the IOKit code as before.
    """
    if not sys.platform.startswith('darwin'):
        return None
    try:
        iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        kIOHIDRequestTypeListenEvent = 1
        request_access = iokit.IOHIDRequestAccess
        request_access.restype = ctypes.c_bool
        request_access.argtypes = [ctypes.c_int]
        return bool(request_access(kIOHIDRequestTypeListenEvent))
    except Exception:
        return None

dp20_pid = 0xd11c
dpp_pid = 0xd11d
all_dp_pids = [dp20_pid, dpp_pid]

def is_duckypad_pid(this_pid):
    return this_pid in all_dp_pids

def get_duckypad_path():
    dp_path_list = set()
    if 'win32' in sys.platform:
        for device_dict in hid.enumerate():
            if device_dict['vendor_id'] == 0x0483 and \
            is_duckypad_pid(device_dict['product_id']) and \
            device_dict['usage'] == 58:
                dp_path_list.add(device_dict['path'])
    else:
        for device_dict in hid.enumerate():
            if device_dict['vendor_id'] == 0x0483 and \
            is_duckypad_pid(device_dict['product_id']):
                dp_path_list.add(device_dict['path'])
    return list(dp_path_list)

PC_TO_DUCKYPAD_HID_BUF_SIZE = 64
DUCKYPAD_TO_PC_HID_BUF_SIZE = 64

HID_RESPONSE_OK = 0
HID_RESPONSE_ERROR = 1
HID_RESPONSE_BUSY = 2
HID_RESPONSE_EOF = 3

def make_dp_info_dict(hid_msg, hid_path):
    this_dict = {}
    this_dict['fw_version'] = f"{hid_msg[3]}.{hid_msg[4]}.{hid_msg[5]}"
    this_dict['dp_model'] = hid_msg[6]
    serial_number_uint32_t = int.from_bytes(hid_msg[7:11], byteorder='big')
    this_dict['serial'] = f'{serial_number_uint32_t:08X}'.upper()
    this_dict['hid_path'] = hid_path
    this_dict['hid_msg'] = hid_msg
    return this_dict

def probe_duckypad_paths(dp_path_list):
    """Return responsive duckyPads and per-path HID failures without losing successes."""
    _ensure_hid_listen_access()
    dp_info_list = []
    errors = []
    pc_to_duckypad_buf = get_empty_pc_to_duckypad_buf()
    for this_path in dp_path_list:
        myh = None
        try:
            myh = hid.device()
            myh.open_path(this_path)
            myh.write(pc_to_duckypad_buf)
            result = myh.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
            if len(result) < 3:
                raise OSError("duckyPad did not return a complete HID response")
            if result[2] != HID_RESPONSE_OK:
                raise OSError(f"duckyPad rejected the HID probe (status {result[2]})")
            dp_info_list.append(make_dp_info_dict(result, this_path))
        except Exception as exc:
            # The Python hid binding reports a bare "OSError: open failed" on
            # macOS; the real IOKit code lives in hidapi's global error string.
            detail = _hidapi_global_error()
            if detail:
                errors.append(f"{type(exc).__name__}: {exc} | hidapi: {detail}")
            else:
                errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            if myh is not None:
                try:
                    myh.close()
                except Exception:
                    pass
    return dp_info_list, errors


def get_all_dp_info(dp_path_list):
    dp_info_list, _errors = probe_duckypad_paths(dp_path_list)
    return dp_info_list

def scan_duckypads():
    all_dp_paths = get_duckypad_path()
    if len(all_dp_paths) == 0:
        return []
    dp_info_list, errors = probe_duckypad_paths(all_dp_paths)
    if not dp_info_list and errors:
        return None
    return sorted(dp_info_list, key=lambda tup: tup['serial'])

def get_empty_pc_to_duckypad_buf():
    ptd_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
    ptd_buf[0] = 5   # HID Usage ID
    return ptd_buf

def hid_txrx(buf_64b, hid_obj):
    # print("\n\nSending to duckyPad:\n", buf_64b)
    hid_obj.write(buf_64b)
    duckypad_to_pc_buf = hid_obj.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
    # print("\nduckyPad response:\n", duckypad_to_pc_buf)
    return duckypad_to_pc_buf

def get_timestamp_and_utc_offset():
    now = datetime.now().astimezone()  # Local time with timezone info
    unix_timestamp = int(now.timestamp())
    utc_offset_minutes = int(now.utcoffset().total_seconds() // 60)
    return unix_timestamp, utc_offset_minutes

def duckypad_sync_rtc(hid_path):
    pc_to_duckypad_buf = get_empty_pc_to_duckypad_buf()
    unix_ts, utc_offset_minutes = get_timestamp_and_utc_offset()
    unix_ts_u8_list = list(unix_ts.to_bytes(4, 'little', signed=False))
    utc_offset_u8_list = list(utc_offset_minutes.to_bytes(2, 'little', signed=True))
    pc_to_duckypad_buf[2] = 0x1A    # Command: Set RTC
    pc_to_duckypad_buf[3] = unix_ts_u8_list[0]
    pc_to_duckypad_buf[4] = unix_ts_u8_list[1]
    pc_to_duckypad_buf[5] = unix_ts_u8_list[2]
    pc_to_duckypad_buf[6] = unix_ts_u8_list[3]
    pc_to_duckypad_buf[7] = utc_offset_u8_list[0]
    pc_to_duckypad_buf[8] = utc_offset_u8_list[1]
    print(pc_to_duckypad_buf)
    myh = hid.device()
    myh.open_path(hid_path)
    result = hid_txrx(pc_to_duckypad_buf, myh)
    myh.close()
    print("duckypad_sync_rtc:", result)

DP_MODEL_OG_DUCKYPAD = 20
DP_MODEL_DUCKYPAD_PRO = 24

class dp_type:
    def __init__(self):
        self.dp20 = DP_MODEL_OG_DUCKYPAD
        self.dp24 = DP_MODEL_DUCKYPAD_PRO
        self.local_dir = 2
        self.usbmsc = 3
        self.hidmsg = 4
        self.unknown = 255
        self.device_type = self.unknown
        self.connection_type = self.unknown
        self.info_dict = None

    def __str__(self):
        return (
            f"dp_type(\n"
            f"  device_type={self.device_type},\n"
            f"  connection_type={self.connection_type},\n"
            f"  info_dict={self.info_dict}\n"
            f")"
        )