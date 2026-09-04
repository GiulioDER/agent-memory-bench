Project memory:

[Evidence item]
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

Recorded: 2026-08-26 12:12:30.393040+00:00
Status: current
Source: sessions__ts-atomic-write__p01.md
[/Evidence item]

[Evidence item]
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

**assistant [Read]**: 
> 1	{"run": 41, "status": "green", "items": [1, 2]}
2

**assistant [Bash]**: 
> ./README.md
./state.json
./store.py
./README.md
./store.py

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant**: There are **no TODO comments** anywhere in the repository. The project consists of only 3 files with minimal code:

- `README.md` — project description
- `store.py` — a small JSON persistence helper
- `state.json` — a run-state data file

Recorded: 2026-08-26 12:10:51.469145+00:00
Status: current
Source: distractors__d029.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# statekeeper
2	
3	A tiny run-state store. `store.py` holds the persistence helpers and `state.json` is the
4	current state file, read at startup by every worker in the fleet.
5	
6	## Getting started
7	
8	### Prerequisites
9	
10	- Python 3.6+
11	
12	### Usage
13	
14	Run the `load()` function from `store.py` to read the current run state:
15	
16	```python
17	from store import load
18	
19	state = load("state.json")
20	print(state)
21	# {'run': 41, 'status': 'green', 'items': [1, 2]}
22	
23	# Access individual values
24	print(state["run"])    # 41
25	print(state["status"]) # green
26	```
27	
28	Or directly from the command line:
29	
30	```bash
31	python -c "from store import load; print(load('state.json'))"
32	```
33

Recorded: 2026-08-26 12:11:25.242378+00:00
Status: current
Source: distractors__d053.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# statekeeper
2	
3	A tiny run-state store. `store.py` holds the persistence helpers and `state.json` is the
4	current state file, read at startup by every worker in the fleet.
5	
6	## Getting started
7	
8	### Prerequisites
9	
10	- Python 3.6+
11	
12	### Usage
13	
14	Clone the repository and use `store.py` to load the current state:
15	
16	```python
17	from store import load
18	
19	state = load("state.json")
20	print(state)  # {'run': 41, 'status': 'green', 'items': [1, 2]}
21	```
22	
23	Or run it directly from the command line:
24	
25	```bash
26	python -c "from store import load; print(load('state.json'))"
27	```
28

**assistant**: Done. I added a "Getting started" section with:

Recorded: 2026-08-26 12:10:18.973541+00:00
Status: current
Source: distractors__d005.md
[/Evidence item]

[Evidence item]
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

Recorded: 2026-08-26 12:12:30.393040+00:00
Status: current
Source: sessions__ts-atomic-write__p01.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# statekeeper

A tiny run-state store. `store.py` holds the persistence helpers and `state.json` is the
current state file, read at startup by every worker in the fleet.
