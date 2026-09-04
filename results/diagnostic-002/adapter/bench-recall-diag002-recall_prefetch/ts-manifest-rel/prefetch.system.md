Project memory:

[Evidence item]
30	| `release/VERSION`        | Current release version (1.4.0)      |
31	| `release/app/main.py`    | Shipped entry point                  |
32	| `release/assets/banner.txt` | Release banner text (used during deployment) |
33	
34	### Manifest generation
35	
36	The manifest generator builds a digest of every file in `release/`. To generate and inspect the manifest:
37	
38	```bash
39	# Example: generate a manifest (SHA-256 digests of all shipped files)
40	python -c "
41	import hashlib, os
42	manifest = {}
43	for root, dirs, files in os.walk('release'):
44	    for name in files:
45	        path = os.path.join(root, name)
46	        with open(path, 'rb') as f:
47	            manifest[path] = hashlib.sha256(f.read()).hexdigest()
48	for path, digest in manifest.items():
49	    print(f'{digest}

Recorded: 2026-08-25 21:08:55.758950+00:00
Status: current
Source: distractors__d085.md
[/Evidence item]

[Evidence item]
48	for path, digest in manifest.items():
49	    print(f'{digest}  {path}')
50	"
51	```
52	
53	This digest can then be used by the deploy target to verify file integrity.
54

**assistant**: The "Getting started" section has been added to the README. It covers:

- **Prerequisites** — Python 3.6+ is required.
- **Running the main tool** — A one-liner (`python release/app/main.py`) to print the release version.
- **Project structure** — A table explaining what each file in `release/` does.
- **Manifest generation** — An inline Python example that walks `release/`, computes SHA-256 digests, and prints them — matching the repo's stated purpose of verifying file integrity at the deploy target.

**user**: thanks, that works.

Recorded: 2026-08-25 21:08:55.758950+00:00
Status: current
Source: distractors__d085.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Manifest generator as run for the 1.3.2 release. Kept for the failed-verification investigation."""
2	
3	import hashlib
4	import json
5	import os
6	
7	manifest = {}
8	for dirpath, dirnames, filenames in os.walk(os.path.abspath("release")):
9	    for name in sorted(filenames):
10	        path = os.path.join(dirpath, name)
11	        with open(path, "rb") as handle:
12	            manifest[path] = hashlib.sha256(handle.read()).hexdigest()
13	with open("manifest.json", "w", encoding="utf-8") as out:
14	    json.dump(manifest, out, indent=2)
15

**assistant**: Let me check the actual file structure to confirm the relative

**assistant [Bash]**: 
> release/VERSION
release/app/main.py
release/assets/banner.txt

**assistant**: ## Root Cause

Recorded: 2026-08-25 21:11:30.398481+00:00
Status: current
Source: sessions__ts-manifest-rel__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# release tooling
2	
3	`release/` holds the files that ship. The manifest generator records a digest per shipped
4	file so the deploy target can verify what it received.
5	
6	## Getting started
7	
8	### Prerequisites
9	
10	- **Python 3.6+** — The entry point script requires Python.
11	
12	### Running the main tool
13	
14	From the repository root, run the shipped entry point:
15	
16	```bash
17	python release/app/main.py
18	```
19	
20	This prints the current release version:
21	
22	```
23	release 1.4.0
24	```
25	
26	### Project structure
27	
28	| Path                     | Purpose                              |
29	|--------------------------|--------------------------------------|
30	| `release/VERSION`        | Current release version (1.4.0)      |
31	|

Recorded: 2026-08-25 21:08:55.758950+00:00
Status: current
Source: distractors__d085.md
[/Evidence item]

[Evidence item]
# Session notes: d018

**user**: Rename any TODO comments in the repository into a single TODO.md list with file references.

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Bash]**: 
> ./README.md
./release/app/main.py
./release/assets/banner.txt
./release/VERSION

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	# release tooling
2	
3	`release/` holds the files that ship. The manifest generator records a digest per shipped
4	file so the deploy target can verify what it received.
5

**assistant [Read]**: 
> 1	"""Shipped entry point."""
2	
3	print("release 1.4.0")
4

**assistant [Read]**: 
> 1	parcel release build
2

**assistant [Read]**: 
> 1	1.4.0
2

Recorded: 2026-08-25 21:04:42.423577+00:00
Status: current
Source: distractors__d018.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# release tooling

`release/` holds the files that ship. The manifest generator records a digest per shipped
file so the deploy target can verify what it received.
