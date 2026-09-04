# Session notes: d024

**user**: Summarise what this project does and what each file in the repository is for, in a short OVERVIEW.md.

**assistant [Bash]**: 
> Exit code 127
/usr/bin/bash: line 1: Get-ChildItem: command not found
/usr/bin/bash: line 1: Select-Object: command not found
/usr/bin/bash: line 1: Format-Table: command not found

**assistant [Bash]**: 
> ./.git/COMMIT_EDITMSG
./.git/config
./.git/description
./.git/HEAD
./.git/hooks/applypatch-msg.sample
./.git/hooks/commit-msg.sample
./.git/hooks/fsmonitor-watchman.sample
./.git/hooks/post-update.sample
./.git/hooks/pre-applypatch.sample
./.git/hooks/pre-commit.sample
./.git/hooks/pre-merge-commit.sample
./.git/hooks/pre-push.sample
./.git/hooks/pre-rebase.sample
./.git/hooks/pre-receive.sample
./.git/hooks/prepare-commit-msg.sample
./.git/hooks/push-to-checkout.sample
./.git/hooks/sendemail-validate.sample
./.git/hooks/update.sample
./.git/index
./.git/info/exclude
./.git/logs/HEAD
./.git/logs/refs/heads/main
./.git/objects/1b/958943b10d36a07e6ade169e9fc12493e4a970
./.git/objects/47/3315c4a7f8c30b6b8d57f24aa6afbe2a291f77
./.git/objects/b0/8b3daa1a6423746ce9542f9ada5ad5b661ed0c
./.git/objects/eb/c4db1a7a6a590d8932e07befcd5ecf7b9f717c
./.git/refs/heads/main
./README.md
./validator.py

**assistant [Read]**: 
> 1	# taskflow intake
2	
3	The intake service accepts task records from client teams and queues them for triage.
4	`validator.py` validates every record before it enters the queue.
5	

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
18	    for field, default in OPTIONAL_FIELDS.items():
19	        validated.setdefault(field, default)
20	    return validated
21	

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant**: Here's a quick summary:

**Taskflow Intake** is a lightweight validation service for task records. Client teams submit task data, and `validator.py` checks every record before it enters the triage queue.

## Files

| File | Purpose |
|------|---------|
| **README.md** | Project overview explaining the intake pipeline and the role of the validator. |
| **validator.py** | Core validation logic. The `validate(record)` function checks that a task record is a `dict`, allows only known fields (`task_id`, `title`, `created_at` — required; `assignee`, `tags` — optional), and returns a validated copy with defaults filled in, or raises `TypeError`/`ValueError` on invalid input. |

The `OVERVIEW.md` has been written to the repo root.

**user**: thanks, that works.
