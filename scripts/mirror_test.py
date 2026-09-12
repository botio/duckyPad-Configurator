#!/usr/bin/env python3
"""Decisive isolation test: does the duckyPad firmware's HID mirror work over
plain cython-hidapi (the same transport the original configurator uses)?

PASS -> firmware is fine, the bug is in the node-hid rewrite.
TIMEOUT/error -> firmware is broken.

Usage (macOS):
    python3 -m pip install hidapi
    python3 mirror_test.py
"""
import sys

try:
    import hid
except ImportError:
    print("install first:  python3 -m pip install hidapi")
    sys.exit(1)

VID, PID = 0x0483, 0xD11C
HID_OPEN_FILE_FOR_READING = 33
HID_READ_FILE = 11


def find_path():
    for i in hid.enumerate():
        if i["vendor_id"] == VID and i["product_id"] == PID:
            return i["path"]
    return None


def write_cmd(dev, cmd, data=b""):
    buf = [0] * 64
    buf[0] = 5  # PC -> duckyPad report ID
    buf[2] = cmd
    for idx, ch in enumerate(data):
        buf[3 + idx] = ch
    dev.write(buf)


path = find_path()
if not path:
    print("NO DEVICE: duckyPad not enumerated (unplug/replug it)")
    sys.exit(1)

dev = hid.device()
try:
    dev.open_path(path)
except OSError as exc:
    detail = ""
    try:
        import ctypes
        lib = ctypes.CDLL(hid.__file__)
        lib.hid_error.restype = ctypes.c_wchar_p
        lib.hid_error.argtypes = [ctypes.c_void_p]
        detail = str(lib.hid_error(None))
    except Exception:
        pass
    print(f"OPEN FAILED: {exc}\nhidapi: {detail}")
    sys.exit(5)
print("opened", path)

# OPEN /profile_info.txt
write_cmd(dev, HID_OPEN_FILE_FOR_READING, b"/profile_info.txt")
resp = dev.read(64, 1500)
if not resp:
    print("TIMEOUT on OPEN_FILE")
    sys.exit(2)
print("OPEN status:", resp[2])

# READ_FILE until EOF
total = 0
while True:
    write_cmd(dev, HID_READ_FILE)
    resp = dev.read(64, 1500)
    if not resp:
        print(f"TIMEOUT on READ_FILE after {total} bytes")
        sys.exit(3)
    if resp[1] != 0:
        print("READ_FILE error:", resp[1])
        sys.exit(4)
    chunk = resp[2]
    if chunk == 0:
        break
    total += chunk

dev.close()
print(f"PASS: profile_info.txt mirrored ({total} bytes) over cython-hidapi")