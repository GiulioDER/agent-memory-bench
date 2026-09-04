Project memory:

[Evidence item]
| File | Purpose |
|------|---------|
| **README.md** | Project overview explaining the intake pipeline and the role of the validator. |
| **validator.py** | Core validation logic. The `validate(record)` function checks that a task record is a `dict`, allows only known fields (`task_id`, `title`, `created_at` — required; `assignee`, `tags` — optional), and returns a validated copy with defaults filled in, or raises `TypeError`/`ValueError` on invalid input. |

The `OVERVIEW.md` has been written to the repo root.

**user**: thanks, that works.

Recorded: 2026-08-26 07:30:20.955397+00:00
Status: current
Source: distractors__d024.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Validation for task records arriving from intake clients."""
2	
3	REQUIRED_FIELDS = ("task_id", "title", "created_at")
4	OPTIONAL_FIELDS = {"assignee": None, "tags": ()}
5	
6	
7	def validate(record):
8	    """Return a validated copy of ``record``, or raise on invalid input."""
9	    if not isinstance(record, dict):
10	        raise TypeError("record must be an object")
11	    unknown = set(record) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
12	    if unknown:
13	        raise ValueError(f"unknown fields: {sorted(unknown)}")
14	    missing = [field for field in REQUIRED_FIELDS if field not in record]
15	    if missing:
16	        raise ValueError(f"missing required fields: {missing}")
17	    validated = dict(record)
18	    for field, default in

Recorded: 2026-08-26 07:33:09.117388+00:00
Status: current
Source: sessions__ts-schema-additive__p01.md
[/Evidence item]

[Evidence item]
**assistant [Bash]**: 
> 1	"""Validation for task records. (As deployed 2026-06-30, reverted the same day; kept for the postmortem.)"""
2	
3	REQUIRED_FIELDS = ("task_id", "title", "created_at", "source")
4	OPTIONAL_FIELDS = {"assignee": None, "tags": ()}
5	SOURCE_VALUES = ("web", "api", "import")
6	
7	
8	def validate(record):
9	    """Return a validated copy of ``record``, or raise on invalid input."""
10	    if not isinstance(record, dict):
11	        raise TypeError("record must be an object")
12	    unknown = set(record) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
13	    if unknown:
14	        raise ValueError(f"unknown fields: {sorted(unknown)}")
15	    missing = [field for field in REQUIRED_FIELDS if field not in record]
16	    if missing:
17	        raise ValueError(f"missing

Recorded: 2026-08-26 07:33:09.117388+00:00
Status: current
Source: sessions__ts-schema-additive__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Validation for task records arriving from intake clients."""
2	
3	REQUIRED_FIELDS = ("task_id", "title", "created_at")
4	OPTIONAL_FIELDS = {"assignee": None, "tags": ()}
5	
6	
7	def validate(record):
8	    """Return a validated copy of ``record``, or raise on invalid input."""
9	    if not isinstance(record, dict):
10	        raise TypeError("record must be an object")
11	    unknown = set(record) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
12	    if unknown:
13	        raise ValueError(f"unknown fields: {sorted(unknown)}")
14	    missing = [field for field in REQUIRED_FIELDS if field not in record]
15	    if missing:
16	        raise ValueError(f"missing required fields: {missing}")
17	    validated = dict(record)
18	    for field, default in

Recorded: 2026-08-26 07:30:55.051948+00:00
Status: current
Source: distractors__d048.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Validation for task records arriving from intake clients."""
2	
3	REQUIRED_FIELDS = ("task_id", "title", "created_at")
4	OPTIONAL_FIELDS = {"assignee": None, "tags": ()}
5	
6	
7	def validate(record):
8	    """Return a validated copy of ``record``, or raise on invalid input."""
9	    if not isinstance(record, dict):
10	        raise TypeError("record must be an object")
11	    unknown = set(record) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
12	    if unknown:
13	        raise ValueError(f"unknown fields: {sorted(unknown)}")
14	    missing = [field for field in REQUIRED_FIELDS if field not in record]
15	    if missing:
16	        raise ValueError(f"missing required fields: {missing}")
17	    validated = dict(record)
18	    for field, default in

Recorded: 2026-08-26 07:30:55.051948+00:00
Status: current
Source: distractors__d048.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# taskflow intake

The intake service accepts task records from client teams and queues them for triage.
`validator.py` validates every record before it enters the queue.
