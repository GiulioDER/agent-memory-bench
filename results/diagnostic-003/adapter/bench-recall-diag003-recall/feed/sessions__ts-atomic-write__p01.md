# Session notes: p01

**user**: Overnight, host wrk-04 was OOM-killed while it was saving run state, and this morning every worker in the fleet refused to start: state.json was half a JSON document. Before restoring from a good copy I preserved the bad file at incident/state.json.bad and the relevant log slice at incident/worker.log. The writer that was running is tools/set_status.py. Work out exactly how the file got into that state, and recommend what our write path must do so that a kill at any instant can never leave the state file unreadable. Recommend, do not implement yet.

**assistant [Read]**: 
> 1	{
2	  "run": 41,
3	  "status": "green",
4	  "items": [
5	    1,
6	    2
7	  ],
8	  "last_deploy": "2026-07-2

**assistant [Read]**: 
> 1	2026-07-21 03:12:07 wrk-04 set_status: writing state.json
2	2026-07-21 03:12:07 wrk-04 kernel: Out of memory: Killed process 2214 (python3) total-vm:812340kB
3	2026-07-21 06:00:12 wrk-01 startup: reading state.json
4	2026-07-21 06:00:12 wrk-01 FATAL json.decoder.JSONDecodeError: Unterminated string starting at: line 8 column 18 (char 96)
5	2026-07-21 06:00:14 wrk-02 startup: reading state.json
6	2026-07-21 06:00:14 wrk-02 FATAL json.decoder.JSONDecodeError: Unterminated string starting at: line 8 column 18 (char 96)
7	

**assistant [Read]**: 
> 1	"""Ops helper: set one status field in state.json."""
2	
3	import json
4	import sys
5	
6	sys.path.insert(0, ".")
7	from store import load
8	
9	
10	def main(key, value):
11	    state = load("state.json")
12	    state[key] = value
13	    with open("state.json", "w", encoding="utf-8") as handle:
14	        json.dump(state, handle, indent=2)
15	
16	
17	if __name__ == "__main__":
18	    main(sys.argv[1], sys.argv[2])
19	

**assistant [Read]**: 
> 1	"""Persistence helpers for the run state."""
2	
3	import json
4	
5	
6	def load(path):
7	    """Read the state dict from ``path``."""
8	    with open(path, encoding="utf-8") as handle:
9	        return json.load(handle)
10	

**assistant**: Now let me see if there are any other relevant files in the project.



**assistant [Bash]**: 
> Exit code 2
ls: cannot access 'C:Usersgde00AppDataLocalTemptmp6j2gmcywproject\': No such file or directory

**assistant [Bash]**: 
> Exit code 2
ls: cannot access '/mnt/c/Users/gde00/AppData/Local/Temp/tmp6j2gmcyw/project/': No such file or directory

**assistant [Bash]**: 
> total 11
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:16 .
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:17 ..
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:17 .git
-rw-r--r-- 1 gde00 197609 170 Aug 23 21:17 README.md
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:16 incident
-rw-r--r-- 1 gde00 197609  48 Aug 23 21:17 state.json
-rw-r--r-- 1 gde00 197609 203 Aug 23 21:17 store.py
drwxr-xr-x 1 gde00 197609   0 Aug 23 21:16 tools

**assistant [Read]**: 
> 1	{"run": 41, "status": "green", "items": [1, 2]}
2	

**assistant [Read]**: 
> 1	# statekeeper
2	
3	A tiny run-state store. `store.py` holds the persistence helpers and `state.json` is the
4	current state file, read at startup by every worker in the fleet.
5	

**assistant**: ## Root-Cause Analysis

### The exact sequence that produced the broken file

1. **`set_status.py`** was invoked to set `last_deploy` to a value like `"2026-07-2..."` (probably `"2026-07-21"` or similar).

2. It called `load("state.json")`, which opened the file for reading, parsed the JSON, and returned a Python dict. That succeeded — the file was intact at that point.

3. It then executed:
   ```python
   with open("state.json", "w", encoding="utf-8") as handle:
       json.dump(state, handle, indent=2)
   ```
   The `"w"` mode **truncated** the file to zero bytes the instant `open(...)` was called.

4. `json.dump` began writing the JSON string. It had written through `"last_deploy": "2026-07-2` (96 bytes, line 8 column 18) when the OOM killer terminated the process.

5. The file was left on disk as a truncated, syntactically invalid JSON document — a valid JSON opening but with an unterminated string.

6. The next morning, every worker in the fleet that called `load("state.json")` on startup hit `json.decoder.JSONDecodeError: Unterminated string starting at: line 8 column 18 (char 96)` and refused to start. **The entire fleet was dead because a single process was killed during a 3-line write.**

### The fundamental flaw

The write path has **no atomicity**: it truncates the live file first, then writes the new content. A kill between truncation and the end of `json.dump` leaves a half-written file that is indistinguishable from a valid file on disk — it exists, has the right name, has plausible content — but is unreadable. There is no way for a reader to distinguish "intentionally empty" from "truncated by a crash."

---

## Recommendation: Atomic Write via Temporary File + Rename

Every write path that touches `state.json` must use the following pattern:

```
1. Write the new JSON to a temporary file in the same directory.
2. fsync the temporary file.
3. Rename the temporary file over state.json (atomic on most filesystems).
```

This guarantees that a reader sees **either the old content or the new content, never partial content**.

### Concrete implementation sketch

**Option A — Add a helper to `store.py`** (preferred, since all writers already import from `store`):

```python
import json
import os
import tempfile


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(path, data):
    """Atomically write *data* (a dict) as JSON to *path*."""
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path) or ".",
        prefix=os.path.basename(path) + ".",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()          # flush Python's internal buffers
            os.fsync(handle.fileno())  # flush OS buffers to disk
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except BaseException:
        os.unlink(tmp_path)         # clean up temp file on failure
        raise
```

**Option B — If you prefer a context manager for clarity:**

```python
@contextmanager
def atomic_write(path):
    """Yield a writable file object; on success, atomically replace *path*."""
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dirpath, prefix=os.path.basename(path) + ".")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        yield f
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
```

Usage in `set_status.py`:

```python
def main(key, value):
    state = load("state.json")
    state[key] = value
    save("state.json", state)          # Option A
    # or
    with atomic_write("state.json"):    # Option B
        json.dump(state, handle, indent=2)
```

### Why this works

| Instant of kill | Result |
|---|---|
| Before `json.dump` starts | Temp file is deleted or left orphaned; `state.json` is untouched |
| Mid-`json.dump` | Temp file is truncated; `state.json` is untouched |
| After `json.dump` completes, before `os.replace` | Temp file is complete; `state.json` is untouched |
| Mid-`os.replace` | Filesystem guarantees the rename is atomic — readers see old or new, never garbage |

### Bonus: fleet-wide resilience

Even with atomic writes, a single OOM kill of a writer can leave a stale `state.json`. Consider also:

- **A reader-side timeout / retry loop** — if a worker can't parse `state.json`, wait a few seconds and retry (in case a writer is in the middle of the atomic write path).
- **A health-check / repair sidecar** — if parsing fails after N retries, fall back to a known-good backup copy (you already proved you have one).

**user**: Agreed. Decision: every state write is atomic from now on. Write the JSON to a temp file in the same directory as state.json, flush and close it, then rename into place with os.replace; never truncate the target file directly. That way a kill at any instant leaves either the old state or the new state on disk, and a torn write can never be observed by a reader.
