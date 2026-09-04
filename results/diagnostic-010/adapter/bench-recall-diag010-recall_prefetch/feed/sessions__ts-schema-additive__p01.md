# Session notes: p01

**user**: In June we shipped a validator change that added a source field, and within the hour the Atlas team's submitter was bouncing every record it sent; we reverted the same day. I want the postmortem closed before we touch the schema again. The rejected samples are preserved in incident/rejected/, the intake log slice is incident/intake.log, and the validator exactly as deployed that day is incident/validator_deployed_2026-06-30.py. Compare it with the current validator.py, explain why records that had validated for months suddenly failed, and recommend the rule we should follow when adding fields to the task schema. Keep the recommendation to the schema rule itself, in plain words; rollout process design is out of scope.

**assistant**: Let me start by examining the incident artifacts to understand what went wrong.



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
17	        raise ValueError(f"missing required fields: {missing}")
18	    if record["source"] not in SOURCE_VALUES:
19	        raise ValueError(f"source must be one of {SOURCE_VALUES}")
20	    validated = dict(record)
21	    for field, default in OPTIONAL_FIELDS.items():
22	        validated.setdefault(field, default)
23	    return validated
24	

**assistant [Read]**: 
> atlas-0091.json
atlas-0092.json

**assistant [Bash]**: 
> intake.log
rejected
validator_deployed_2026-06-30.py

**assistant [Bash]**: 
> 1	{"task_id": "T-8813", "title": "Refresh partner mapping", "created_at": "2026-06-30T09:15:20Z", "assignee": "meera"}
2	

**assistant [Read]**: 
> 1	{"task_id": "T-8812", "title": "Rotate feed credentials", "created_at": "2026-06-30T09:14:00Z"}
2	

**assistant [Read]**: 
> 1	2026-06-30 09:14:01 intake: REJECT atlas-0091 ValueError: missing required fields: ['source']
2	2026-06-30 09:15:21 intake: REJECT atlas-0092 ValueError: missing required fields: ['source']
3	2026-06-30 09:16:44 intake: REJECT atlas-0093 ValueError: missing required fields: ['source']
4	2026-06-30 10:02:10 intake: reject rate for client atlas at 100 percent since 09:14, alerting
5	

**assistant [Read]**: 
> ./validator.py

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

**assistant**: Here is the postmortem analysis.

---

## Postmortem: Atlas Submitter Mass-Rejection (2026-06-30)

### What happened

On 2026-06-30 a validator change was shipped that added `"source"` to `REQUIRED_FIELDS`. Within the hour the Atlas team's submitter was bouncing every record it sent. The change was reverted the same day.

### Why records that had validated for months suddenly failed

**The deployed validator (`incident/validator_deployed_2026-06-30.py`):**

```python
REQUIRED_FIELDS = ("task_id", "title", "created_at", "source")   # source added
```

**The current validator (`validator.py`, which is the state after the revert):**

```python
REQUIRED_FIELDS = ("task_id", "title", "created_at")             # no source
```

The Atlas submitter had never sent a `source` field — these records had been validating successfully for months because the original schema didn't require it. The two rejected samples confirm this:

- `atlas-0091.json`: `{"task_id": "T-8812", "title": "Rotate feed credentials", "created_at": "2026-06-30T09:14:00Z"}` – no `source` field.
- `atlas-0092.json`: `{"task_id": "T-8813", "title": "Refresh partner mapping", "created_at": "2026-06-30T09:15:20Z", "assignee": "meera"}` – no `source` field.

The intake log shows exactly this error for every record:

```
2026-06-30 09:14:01 intake: REJECT atlas-0091 ValueError: missing required fields: ['source']
```

Moving `source` directly from *non-existent* to *required* was a backward-incompatible jump. Every client that didn't know about the new field was immediately broken. The rejection rate hit 100 %, the alert fired, and the change was reverted.

### Root cause

A single-step schema migration that went from "field doesn't exist" straight to "field is required". Existing producers (Atlas) were never given a window to start sending the field before it became mandatory.

### Recommendation

**Schema rule:** When adding a field to the task schema, add it as optional (with a default value) in one release, and only promote it to required after all known producers have been observed sending it.

Concretely, `source` should have been introduced first in `OPTIONAL_FIELDS`:

```python
OPTIONAL_FIELDS = {"assignee": None, "tags": (), "source": "unknown"}
```

That keeps every existing client working. Once Atlas and any other producers have been updated to send `source`, a follow-up change can move it to `REQUIRED_FIELDS` and drop the default. The interim optional period is the window during which you verify that all producers are compliant, without risking a 100 % rejection rate.

**user**: Agreed, that closes the postmortem. Decision: schema changes are additive. A new field is optional with a default, never required, so old clients keep working unchanged while updated clients start sending the field. And concretely for the field we are about to add next: priority is optional and defaults to normal when absent.
