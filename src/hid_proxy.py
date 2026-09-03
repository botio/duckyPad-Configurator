"""Proxy for the ``hid`` (cython-hidapi) module that routes HID calls through
the Electron main process over a Unix domain socket.

Why: on macOS the Input Monitoring TCC grant is keyed to the .app's main
executable. The Python sidecar is a *different* ad-hoc binary, so its own
``IOHIDDeviceOpen`` fails with ``kIOReturnNotPrivileged`` even though the
``.app`` is granted. The Electron main process *is* the granted binary, so
performing the open (and I/O) there succeeds. This module presents the same
API as ``hid`` (``enumerate`` / ``device`` with ``open_path`` / ``write`` /
``read`` / ``close``); on macOS with the socket available it forwards each
call to the main process, otherwise it delegates to the real ``hid`` module
so Linux/Windows and dev mode are unchanged.

The socket channel is separate from the sidecar's stdio RPC on purpose: the
RPC dispatcher runs with ``stdout`` redirected to ``stderr``, so a proxy that
wrote to ``sys.stdout`` mid-dispatch would never reach the main process.
"""

import base64
import json
import os
import socket
import sys

__all__ = ["device", "enumerate"]

_sock_path = None
_conn = None
_real_hid = None


def _real():
    """Lazily import the real cython-hidapi module (fallback / non-macOS)."""
    global _real_hid
    if _real_hid is None:
        import hid as _h
        _real_hid = _h
    return _real_hid


def _path():
    global _sock_path
    if _sock_path is None:
        _sock_path = os.environ.get("DUCKYPAD_HID_SOCK")
    return _sock_path


def _active():
    """Proxy is used only on macOS when the main process exposed a socket."""
    return sys.platform.startswith("darwin") and bool(_path())


def _connect():
    global _conn
    if _conn is not None:
        return _conn
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(_path())
        _conn = s
        return s
    except OSError:
        _conn = None
        raise


def _b64(data: bytes) -> str:
    return base64.b64encode(bytes(data)).decode("ascii")


def _from_b64(text) -> bytes:
    if text is None:
        return b""
    return base64.b64decode(text)


def _request(payload):
    """Send one request, read one response. Raises OSError on failure."""
    conn = _connect()
    try:
        conn.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                raise OSError("main process closed the HID socket")
            buf += chunk
        resp = json.loads(buf.decode("utf-8"))
    except OSError:
        # Connection is suspect; drop it so the next call reconnects.
        try:
            conn.close()
        except Exception:
            pass
        _reset_conn()
        raise
    if "error" in resp and resp["error"]:
        raise OSError(str(resp["error"]))
    return resp


def _reset_conn():
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
    _conn = None


class _Device:
    def __init__(self):
        self._handle = None

    def open_path(self, path):
        if isinstance(path, bytes):
            path_b64 = _b64(path)
        else:
            path_b64 = _b64(str(path).encode("utf-8"))
        resp = _request({"op": "open", "path": path_b64})
        self._handle = resp["handle"]

    def write(self, buff):
        data = bytes(buff)
        resp = _request({"op": "write", "handle": self._handle, "data": _b64(data)})
        return int(resp.get("result", len(data)))

    def read(self, max_length, timeout_ms=None):
        resp = _request({"op": "read", "handle": self._handle, "max": int(max_length), "timeout": timeout_ms})
        data = _from_b64(resp.get("data"))
        # Match cython-hidapi: return a list of ints (empty list on timeout).
        return list(data)

    def close(self):
        if self._handle is None:
            return
        handle = self._handle
        self._handle = None
        try:
            _request({"op": "close", "handle": handle})
        except OSError:
            pass

    def set_nonblocking(self, flag):
        # Not meaningful through the proxy; the main process reads are
        # already non-blocking (event-driven). Kept for API parity.
        return None

    # Delegate any other attribute to the real device so we don't surprise
    # callers that use less common methods.
    def __getattr__(self, name):
        return getattr(_real().device(), name)


def device():
    if _active():
        return _Device()
    return _real().device()


def enumerate():
    if not _active():
        return _real().enumerate()
    resp = _request({"op": "enumerate"})
    out = []
    for d in resp.get("devices", []):
        out.append({
            "vendor_id": d.get("vendor_id"),
            "product_id": d.get("product_id"),
            "usage": d.get("usage", 0),
            "usage_page": d.get("usage_page", 0),
            "path": _from_b64(d.get("path")),
            "serial_number": d.get("serial_number"),
            "manufacturer": d.get("manufacturer"),
            "product": d.get("product"),
        })
    return out


def hid_error():
    """Presented like hidapi's global error hook; the main process's errors
    arrive as raised OSError messages instead, so this is always empty."""
    return None
