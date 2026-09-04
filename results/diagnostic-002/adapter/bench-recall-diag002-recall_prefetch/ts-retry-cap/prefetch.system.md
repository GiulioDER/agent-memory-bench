Project memory:

[Evidence item]
retrying, inter-attempt interval 1.000s on every host, attempts aligned to the second
9

**assistant [Read]**: 
> 1	"""client.py retry patch as deployed 2026-08-10, reverted 2026-08-13. Kept for the incident review."""
2	
3	import time
4	
5	
6	class TransportError(Exception):
7	    """Raised by a transport when a fetch attempt fails."""
8	
9	
10	def fetch(url, transport, sleep=time.sleep):
11	    """Fetch ``url`` via ``transport``, retrying until it answers."""
12	    while True:
13	        try:
14	            return transport(url)
15	        except TransportError:
16	            sleep(1.0)
17

**assistant**: Let me also check if there's an existing `client.py` to understand what the codebase currently looks like.

**assistant [Bash]**: 
> Exit code 2
client.py

Recorded: 2026-08-25 21:11:52.221006+00:00
Status: current
Source: sessions__ts-retry-cap__p01.md
[/Evidence item]

[Evidence item]
**assistant [Bash]**: 
> a47789b fixture

**assistant [Read]**: 
> 1	"""Feed fetching for the syncer."""
2	
3	import time
4	
5	
6	class TransportError(Exception):
7	    """Raised by a transport when a fetch attempt fails."""
8	
9	
10	def fetch(url, transport, sleep=time.sleep):
11	    """Fetch ``url`` via ``transport`` and return its response text."""
12	    return transport(url)
13

**assistant**: ## Analysis

### Root Cause: Why every instance retried in lockstep

The deployed patch (`retry_patch_reverted.py`) uses a fixed 1.0-second sleep:

```python
except TransportError:
    sleep(1.0)
```

Recorded: 2026-08-25 21:11:52.221006+00:00
Status: current
Source: sessions__ts-retry-cap__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Feed fetching for the syncer."""
2	
3	import time
4	
5	
6	class TransportError(Exception):
7	    """Raised by a transport when a fetch attempt fails."""
8	
9	
10	def fetch(url, transport, sleep=time.sleep):
11	    """Fetch ``url`` via ``transport`` and return its response text."""
12	    return transport(url)
13

**assistant**: The repository contains only one Python file: `client.py`. Let me inspect its full content:

```python
"""Feed fetching for the syncer."""

import time

class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""

def fetch(url, transport, sleep=time.sleep):
    """Fetch ``url`` via ``transport`` and return its response text."""
    return transport(url)
```

Recorded: 2026-08-25 21:05:01.581542+00:00
Status: current
Source: distractors__d022.md
[/Evidence item]

[Evidence item]
Replace `client.py`'s current one-shot fetch (or the reverted patch) with a retry loop that uses **exponential backoff with full jitter** — the standard approach from the [AWS exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) article. This spreads retries across time so that even if N hosts fail at the same moment, they never retry in lockstep again.

```python
"""client.py — Feed fetching for the syncer."""

import random
import time

class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""

class RateLimitError(TransportError):
    """Raised when the server returns HTTP 429 (Too Many Requests)."""

Recorded: 2026-08-25 21:11:52.221006+00:00
Status: current
Source: sessions__ts-retry-cap__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# syncer
2	
3	Pulls partner feeds on a schedule. `client.py` wraps the transport layer; a transport is any
4	callable taking a url and returning the response text, raising TransportError on failure.
5	
6	## Getting started
7	
8	### Prerequisites
9	
10	- Python 3.14+
11	
12	### Usage
13	
14	The library exposes two things from `client.py`:
15	
16	- **`fetch(url, transport)`** — fetches a URL using the given transport callable.
17	- **`TransportError`** — exception raised by a transport on failure.
18	
19	A transport is any callable that accepts a URL string and returns the response text. The
20	simplest transport is `urllib.request.urlopen`:
21	
22	```python
23	from urllib.request import urlopen
24	from client import fetch
25	
26	def my_transport(url):
27	    with

Recorded: 2026-08-25 21:06:38.826814+00:00
Status: current
Source: distractors__d046.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# syncer

Pulls partner feeds on a schedule. `client.py` wraps the transport layer; a transport is any
callable taking a url and returning the response text, raising TransportError on failure.
