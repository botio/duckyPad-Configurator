from __future__ import annotations

import contextlib
import json
from pathlib import Path
import signal
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Legacy core modules emit diagnostic prints during import. stdout is reserved
# for NDJSON responses, so route their diagnostics to stderr from the outset.
with contextlib.redirect_stdout(sys.stderr):
    from core.service import CoreError, CoreService

_running = True
_protocol_stdout = sys.stdout
_active_request: dict[str, Any] | None = None


def _write(payload: dict[str, Any]) -> None:
    _protocol_stdout.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    _protocol_stdout.flush()


def _emit(method: str, params: dict[str, Any]) -> None:
    if method == "event/profiles/save" and _active_request is not None:
        params = {**params, "request_id": _active_request["id"]}
    _write({"jsonrpc": "2.0", "method": method, "params": params})


def _stop(_signum: int, _frame: Any) -> None:
    # sys.stdin iteration blocks in C; setting a flag cannot wake it. Raising
    # exits immediately so Electron can shut the sidecar down deterministically.
    raise SystemExit(0)


def main() -> int:
    global _running, _active_request
    signal.signal(signal.SIGTERM, _stop)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _stop)
    with contextlib.redirect_stdout(sys.stderr):
        service = CoreService(emit=_emit)
    for raw in sys.stdin:
        if not _running:
            break
        try:
            request = json.loads(raw)
            if request.get("jsonrpc") != "2.0" or "id" not in request or not isinstance(request.get("method"), str):
                raise CoreError(-32600, "Invalid JSON-RPC request")
            _active_request = request
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = service.dispatch(request["method"], request.get("params") or {})
            finally:
                _active_request = None
            _write({"jsonrpc": "2.0", "id": request["id"], "result": result})
        except CoreError as error:
            _write({"jsonrpc": "2.0", "id": request.get("id") if "request" in locals() else None, "error": {"code": error.code, "message": error.message, "data": error.data}})
        except json.JSONDecodeError:
            _write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error", "data": {}}})
        except Exception as error:  # keep RPC transport alive for renderer recovery
            detail = f"{type(error).__name__}: {error}"
            print(f"sidecar internal error: {detail}", file=sys.stderr, flush=True)
            _write({"jsonrpc": "2.0", "id": request.get("id") if "request" in locals() else None, "error": {"code": -32603, "message": f"Internal sidecar error: {detail}", "data": {"detail": detail}}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
