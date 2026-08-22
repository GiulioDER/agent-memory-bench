"""Drive the produced store.save under instrumented io/os and report the write pattern.

Instrumentation is installed BEFORE ``store`` is imported, so even a ``from os import
replace`` at module top binds the recording wrapper. Temp-file machinery (tempfile.mkstemp,
NamedTemporaryFile, plain open of a sibling path) passes through untouched: only a write-mode
open of the TARGET itself, or the absence of any rename landing on it, is a violation.
"""

import builtins
import io
import json
import os
import sys
from pathlib import Path

TARGET = Path("state.json").resolve()
NEW_STATE = {"run": 42, "status": "amber", "items": [1, 2, 3]}

direct_writes = []
rename_destinations = []


def _resolve(candidate):
    try:
        return Path(os.fspath(candidate)).resolve()
    except TypeError:
        return None


_true_open = builtins.open


def _recording_open(file, mode="r", *args, **kwargs):
    if _resolve(file) == TARGET and any(flag in str(mode) for flag in "wax+"):
        direct_writes.append(f"open(..., {mode!r})")
    return _true_open(file, mode, *args, **kwargs)


_true_os_open = os.open
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_TRUNC


def _recording_os_open(path, flags, *args, **kwargs):
    if _resolve(path) == TARGET and flags & _WRITE_FLAGS:
        direct_writes.append(f"os.open(..., {flags:#o})")
    return _true_os_open(path, flags, *args, **kwargs)


def _recording_rename(true_rename):
    def rename(src, dst, *args, **kwargs):
        rename_destinations.append(_resolve(dst))
        return true_rename(src, dst, *args, **kwargs)

    return rename


builtins.open = _recording_open
io.open = _recording_open
os.open = _recording_os_open
os.replace = _recording_rename(os.replace)
os.rename = _recording_rename(os.rename)

sys.path.insert(0, str(Path.cwd()))
import store  # instrumentation must be in place before this import

store.save("state.json", NEW_STATE)

with _true_open(TARGET, encoding="utf-8") as handle:
    written = json.load(handle)
if written != NEW_STATE:
    print(f"VERDICT WRONG_CONTENT {written!r}")
    sys.exit(2)
if direct_writes:
    print(f"VERDICT DIRECT_WRITE {direct_writes}")
    sys.exit(3)
if TARGET not in rename_destinations:
    print("VERDICT NO_RENAME")
    sys.exit(4)
print("VERDICT ATOMIC_OK")
