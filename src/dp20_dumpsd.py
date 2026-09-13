import os
import shutil
import time

import hid_proxy as hid
from shared import *


DP20_KEY_COUNT = 20
DP20_RESPONSE_TIMEOUT_MS = 1500


class LocalMirrorError(OSError):
    """The local profile mirror could not be created or written."""


def _read_response(hid_obj, operation):
    response = hid_obj.read(
        DUCKYPAD_TO_PC_HID_BUF_SIZE, DP20_RESPONSE_TIMEOUT_MS
    )
    if not response:
        raise OSError(
            f"{operation} timed out after {DP20_RESPONSE_TIMEOUT_MS} ms"
        )
    if len(response) != DUCKYPAD_TO_PC_HID_BUF_SIZE:
        raise OSError(f"{operation} response is incomplete")
    return response




def save_to_file(sd_path, pc_dump_dir_path, file_name, file_content):
    sd_path = sd_path.lstrip("\\/")
    full_dir_path = os.path.join(pc_dump_dir_path, sd_path)
    full_file_path = os.path.join(full_dir_path, file_name)
    try:
        os.makedirs(full_dir_path, exist_ok=True)
        with open(full_file_path, 'wb') as file:
            file.write(file_content)
    except OSError as exc:
        raise LocalMirrorError(exc.errno, exc.strerror, exc.filename) from exc


def hid_dump_file(sd_file_path, hid_obj, missing_ok=False):
    if len(sd_file_path) > HID_READ_FILE_PATH_SIZE_MAX:
        raise OSError("SD file path too long")

    pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
    pc_to_duckypad_buf[0] = 5
    pc_to_duckypad_buf[2] = HID_COMMAND_OPEN_FILE_FOR_READING
    for index, value in enumerate(sd_file_path):
        pc_to_duckypad_buf[3 + index] = ord(value)

    hid_obj.write(pc_to_duckypad_buf)
    duckypad_to_pc_buf = _read_response(hid_obj, "HID open file")
    status = duckypad_to_pc_buf[2]
    if status != 0:
        if missing_ok and status in (4, 5):
            return None
        raise OSError(f"HID open file for read failed: {status}")

    all_data = bytearray()
    while True:
        pc_to_duckypad_buf[2] = HID_COMMAND_READ_FILE
        hid_obj.write(pc_to_duckypad_buf)
        duckypad_to_pc_buf = _read_response(hid_obj, "HID read file")
        if duckypad_to_pc_buf[1] != 0:
            raise OSError(f"HID read file failed: {duckypad_to_pc_buf[1]}")
        chunk_size = duckypad_to_pc_buf[2]
        # Report ID, status, and chunk length occupy the first three bytes.
        if chunk_size > len(duckypad_to_pc_buf) - 3:
            raise OSError(f"HID read file returned invalid chunk size: {chunk_size}")
        if chunk_size == 0:
            return bytes(all_data)
        all_data.extend(duckypad_to_pc_buf[3:3 + chunk_size])


def _profile_names(profile_info):
    names = []
    for line in profile_info.decode("utf-8", "replace").splitlines():
        number, separator, name = line.strip().partition(" ")
        if separator and number.isdecimal() and name:
            names.append(name)
    return names


def _dump_profile(profile_name, dump_dir_path, hid_obj, tk_root_obj, ui_text_obj):
    profile_dir = f"/profile_{profile_name}"
    config = hid_dump_file(f"{profile_dir}/config.txt", hid_obj)
    save_to_file(profile_dir, dump_dir_path, "config.txt", config)

    for key_number in range(1, DP20_KEY_COUNT + 1):
        for suffix in (".txt", "-release.txt"):
            file_name = f"key{key_number}{suffix}"
            content = hid_dump_file(f"{profile_dir}/{file_name}", hid_obj, missing_ok=True)
            if content is None:
                continue
            ui_print(f"Loading {profile_dir}/{file_name}", tk_root_obj, ui_text_obj)
            save_to_file(profile_dir, dump_dir_path, file_name, content)


def _exit_file_access_mode(hid_obj):
    packet = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
    packet[0] = 5
    packet[2] = HID_COMMAND_EXIT_FILE_ACCESS
    try:
        hid_obj.write(packet)
        response = _read_response(hid_obj, "EXIT_FILE_ACCESS")
        if response[2] != 0:
            raise OSError("EXIT_FILE_ACCESS was not acknowledged")
        return True
    except OSError as exc:
        print("DP20 direct mirror completed but could not exit File Access Mode:", exc)
        return False

def _dump_sd_once(dp_path, dump_dir_path, tk_root_obj, ui_text_obj):
    dp20_h = None
    opened = False
    failure = None
    exited = True
    try:
        dp20_h = hid.device()
        dp20_h.open_path(dp_path)
        opened = True
        profile_info = hid_dump_file(f"/{profile_info_dot_txt}", dp20_h)
        save_to_file("", dump_dir_path, profile_info_dot_txt, profile_info)
        for profile_name in _profile_names(profile_info):
            _dump_profile(profile_name, dump_dir_path, dp20_h, tk_root_obj, ui_text_obj)

        header = hid_dump_file(f"/{user_header_dot_txt}", dp20_h, missing_ok=True)
        if header is not None:
            save_to_file("", dump_dir_path, user_header_dot_txt, header)
    except OSError as exc:
        failure = exc
    finally:
        if dp20_h is not None:
            exited = _exit_file_access_mode(dp20_h) if opened else True
            dp20_h.close()
        if opened and not exited:
            recovery_h = None
            try:
                recovery_h = hid.device()
                recovery_h.open_path(dp_path)
                exited = _exit_file_access_mode(recovery_h)
            except OSError as exc:
                print("DP20 File Access Mode recovery failed:", exc)
                exited = False
            finally:
                if recovery_h is not None:
                    recovery_h.close()

    if failure is not None:
        raise failure
    if not exited:
        raise OSError("EXIT_FILE_ACCESS failed on both HID handles")


def dump_sd(dp_path, dump_dir_path, backup_dir_path, tk_root_obj=None, ui_text_obj=None):
    """Build a DP20 profile mirror, retrying the whole transaction on HID failure."""
    del backup_dir_path
    last_error = None
    for attempt in range(1, 4):
        try:
            shutil.rmtree(dump_dir_path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise LocalMirrorError(exc.errno, exc.strerror, exc.filename) from exc
        try:
            _dump_sd_once(dp_path, dump_dir_path, tk_root_obj, ui_text_obj)
            return True
        except LocalMirrorError:
            raise
        except OSError as exc:
            last_error = exc
            print(f"DP20 direct file mirror attempt {attempt}/3 failed:", exc)
            if attempt < 3:
                time.sleep(0.15)
    raise OSError(f"DP20 profile mirror failed after 3 attempts: {last_error}") from last_error

