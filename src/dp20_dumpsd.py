import os
import hid_proxy as hid
import time
import shutil
import scan_md5
from shared import *

def millis():
    return time.time_ns() // 1000000

SD_WALK_OP_TYPE_INDEX = 1

SD_WALK_OP_ACK = 0
SD_WALK_OP_NEW_DIR = 1
SD_WALK_OP_FILE_CONTENT = 2
SD_WALK_OP_FILE_MD5 = 3
SD_WALK_OP_EOT = 4

def read_binary_file(file_path):
    with open(file_path, 'rb') as file:
        return file.read()

def save_to_file(sd_path, pc_dump_dir_path, file_name, file_content):
    sd_path = sd_path.lstrip("\\/")
    # print("save_to_file:", sd_path, pc_dump_dir_path, file_name, file_content)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_dir_path = os.path.join(script_dir, pc_dump_dir_path, sd_path)
    full_file_path = os.path.join(full_dir_path, file_name)
    os.makedirs(full_dir_path, exist_ok=True)
    with open(full_file_path, 'wb') as file:
        file.write(file_content)

def hid_dump_file(sd_file_path, hid_obj):
    if len(sd_file_path) > HID_READ_FILE_PATH_SIZE_MAX:
        raise OSError("SD file path too long")

    print(f'Reading file: {sd_file_path} ', end='')

    pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
    pc_to_duckypad_buf[0] = 5   # HID Usage ID, always 5
    pc_to_duckypad_buf[1] = 0   # unused
    pc_to_duckypad_buf[2] = HID_COMMAND_OPEN_FILE_FOR_READING # Command type

    for index, value in enumerate(sd_file_path):
        pc_to_duckypad_buf[3+index] = ord(value)

    hid_obj.write(pc_to_duckypad_buf)
    duckypad_to_pc_buf = hid_obj.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
    if duckypad_to_pc_buf[2] != 0:
        raise OSError("HID open file for read failed")

    all_data = []
    while 1:
        pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
        pc_to_duckypad_buf[0] = 5   # HID Usage ID, always 5
        pc_to_duckypad_buf[1] = 0   # unused
        pc_to_duckypad_buf[2] = HID_COMMAND_READ_FILE
        hid_obj.write(pc_to_duckypad_buf)
        duckypad_to_pc_buf = hid_obj.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
        chunk_size = duckypad_to_pc_buf[2]
        if chunk_size == 0:
            break
        all_data += duckypad_to_pc_buf[3:3+chunk_size]
        print(len(all_data), " ", end='')

    print()
    return bytes(all_data)

DP_VENDOR_ID = 0x0483
DP_PIDS = (0xd11c, 0xd11d)   # duckyPad OG (20) and Pro (24)

def _find_dp20_path(prefer_path, timeout_ms=12000):
    """After a SW_RESET the duckyPad reboots and re-enumerates; its HID path may
    change. Poll hid.enumerate() for a duckyPad (vendor 0x0483 + a DP PID) and
    return its path, preferring prefer_path if it still appears. Returns None
    if the pad does not re-appear within the timeout."""
    deadline = millis() + timeout_ms
    while millis() < deadline:
        found = []
        try:
            for dev in hid.enumerate():
                if dev.get("vendor_id") == DP_VENDOR_ID and dev.get("product_id") in DP_PIDS:
                    p = dev.get("path")
                    if p:
                        found.append(p)
        except Exception:
            pass
        if found:
            if prefer_path in found:
                return prefer_path
            return found[0]
        time.sleep(0.2)
    return None

def _sw_reset_and_reopen(dp_path):
    """Reboot the duckyPad via SW_RESET so its boot-time scan_profiles() re-runs
    and repopulates profile_name_list, then re-open it.

    The firmware's DUMP_SD handler calls find_first_profile() and hard-faults
    ("Fatal Error:10", all keys lit, infinite hang, no HID response) when
    profile_name_list is empty. That list is only written during main()'s boot
    (mount_sd -> ensure_new_profile_format -> scan_profiles), while the custom-HID
    interface is live before the scan completes. If DUMP_SD arrives before the
    scan finishes, the pad bricks itself. Rebooting first guarantees a fresh,
    complete scan before the dump.

    Returns the reopened hid device, or None if the flow failed.
    """
    sw_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
    sw_buf[0] = 5                    # HID Usage ID (OUT report)
    sw_buf[1] = 0
    sw_buf[2] = HID_COMMAND_SW_RESET  # 20
    dp = hid.device()
    try:
        dp.open_path(dp_path)
    except Exception as exc:
        print("pre-scan: open failed:", exc)
        return None
    try:
        dp.write(sw_buf)
        try:
            ack = dp.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
            print("pre-scan: SW_RESET ack:", list(ack[:4]) if ack else None)
        except Exception as exc:
            print("pre-scan: read ack (pad mid-reset):", exc)
    finally:
        try:
            dp.close()
        except Exception:
            pass
    new_path = _find_dp20_path(dp_path)
    if new_path is None:
        print("pre-scan: duckyPad did not re-enumerate after SW_RESET")
        return None
    # Give the rebooted pad time to finish its boot-time profile scan
    # (f_mount + ensure_new_profile_format + scan_profiles) before DUMP_SD.
    print("pre-scan: re-enumerated at", new_path, "- waiting for boot to settle")
    time.sleep(5)
    try:
        dp.open_path(new_path)
    except Exception as exc:
        print("pre-scan: re-open failed:", exc)
        return None
    return dp

def dump_sd(dp_path, dump_dir_path, backup_dir_path, tk_root_obj=None, ui_text_obj=None):
    current_dir = None
    pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
    pc_to_duckypad_buf[0] = 5   # HID Usage ID, always 5
    pc_to_duckypad_buf[1] = 0   # unused
    pc_to_duckypad_buf[2] = HID_COMMAND_DUMP_SD # Command type

    shutil.rmtree(dump_dir_path, ignore_errors=True)
    backup_md5_dict = scan_md5.get_md5_dict(backup_dir_path)
    md5_miss_list = []

    # Ensure the pad has completed its boot-time profile scan before the dump:
    # reboot it via SW_RESET (re-runs scan_profiles, repopulating
    # profile_name_list), wait for it to re-enumerate and settle, then re-open.
    # If the pre-scan flow fails, fall back to a plain open (legacy behavior).
    dp20_h = _sw_reset_and_reopen(dp_path)
    if dp20_h is None:
        dp20_h = hid.device()
        dp20_h.open_path(dp_path)

    while 1:
        dp20_h.write(pc_to_duckypad_buf)
        duckypad_to_pc_buf = dp20_h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)

        if len(duckypad_to_pc_buf) != DUCKYPAD_TO_PC_HID_BUF_SIZE:
            dp20_h.close()
            return False

        if duckypad_to_pc_buf[SD_WALK_OP_TYPE_INDEX] == SD_WALK_OP_ACK:
            continue

        elif duckypad_to_pc_buf[SD_WALK_OP_TYPE_INDEX] == SD_WALK_OP_EOT:
            break

        elif duckypad_to_pc_buf[SD_WALK_OP_TYPE_INDEX] == SD_WALK_OP_NEW_DIR:
            rawchar = duckypad_to_pc_buf[2:]
            current_dir = ''.join(chr(c) for c in rawchar[:rawchar.index(0)])
            print(current_dir)

        elif duckypad_to_pc_buf[SD_WALK_OP_TYPE_INDEX] == SD_WALK_OP_FILE_MD5:
            rawchar = duckypad_to_pc_buf[18:]
            this_file_name = ''.join(chr(c) for c in rawchar[:rawchar.index(0)])
            md5_list = duckypad_to_pc_buf[2:18]
            md5_string = ''.join(f'{x:02x}' for x in md5_list)
            print(this_file_name, md5_string)
            ui_print(f"Loading {current_dir}/{this_file_name}", tk_root_obj, ui_text_obj)
            if md5_string in backup_md5_dict:
                cached_file_content = read_binary_file(backup_md5_dict[md5_string])
                save_to_file(current_dir, dump_dir_path, this_file_name, cached_file_content)
            else:
                md5_miss_list.append((current_dir, this_file_name))

        elif duckypad_to_pc_buf[SD_WALK_OP_TYPE_INDEX] == SD_WALK_OP_FILE_CONTENT:
            file_name_end = duckypad_to_pc_buf[2] + 1
            file_content_end = duckypad_to_pc_buf[3] + 1
            raw_filename_list = duckypad_to_pc_buf[4:file_name_end]
            this_file_name = ''.join(chr(c) for c in raw_filename_list[:raw_filename_list.index(0)])
            print(this_file_name)
            ui_print(f"Loading {current_dir}/{this_file_name}", tk_root_obj, ui_text_obj)
            raw_file_content_bytes = bytes(duckypad_to_pc_buf[file_name_end:file_content_end])
            save_to_file(current_dir, dump_dir_path, this_file_name, raw_file_content_bytes)

    md5_miss_list.append(('', profile_info_dot_txt, user_header_dot_txt))
    for item in md5_miss_list:
        sd_dir = item[0]
        sd_file_name = item[1]
        print("MD5 MISS:", sd_dir, sd_file_name)
        ui_print(f"Loading {sd_dir}/{sd_file_name}", tk_root_obj, ui_text_obj)
        raw_bytes = hid_dump_file(f'{sd_dir}/{sd_file_name}', dp20_h)
        save_to_file(sd_dir, dump_dir_path, sd_file_name, raw_bytes)

    dp20_h.close()
    return True

