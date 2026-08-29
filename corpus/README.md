# The experience corpus

The neutral feed every memory product ingests through its own write path. One file per
session, JSON lines: `{"role", "content", "tool_name?", "tool_input?", "tool_result?", "ts"}`.

Three rules, enforced by tooling:

1. **Content is verbatim agent output.** Sessions are recorded live by
   `scripts/record_precursor.py` running Claude Code against a staged incident
   (`tasks/<id>/precursors/<name>/`). A recording that fails to surface the fact is
   re-staged and re-run, never edited. The one authored turn is the closing user
   confirmation (`followup.txt`), which states the decision the way a real user closes such
   a session.
2. **Timestamps are recording metadata mapped onto the project timeline** (session date from
   the recording plan, 40 seconds per turn from 09:00 UTC), so the corpus reads as weeks of
   history rather than one recording afternoon. Disclosed here; identical bytes for every
   product; `manifest.json` carries the sha256 of every file.
3. **Each governing fact lives in exactly one task's sessions.** `scripts/audit_corpus.py`
   asserts presence (the task's own sessions state it), containment (no other task's
   sessions or distractors do), and locus (neither the fixture nor the CLAUDE.md bundle do).

   A `xs-*` task's fact is **distributed across its own sessions**, one share per session, and
   the audit adds a fourth assertion for it: each shard states its own share and no session
   states another's. For `evolve` that runs forwards only, since the session that supersedes a
   value names the value it replaces. `scripts/record_precursor.py` enforces the same rule while
   recording, so a session that wandered into the other half is refused rather than ingested.
   See `docs/CROSS_SESSION_SYNTHESIS.md`.

`sessions/<task_id>/` holds precursors; `distractors/` holds mundane sessions establishing
no governing fact, recorded the same way (`scripts/record_distractor.py`), targeting a
distractor-to-signal ratio of at least 4:1.

Because content is verbatim, tool results carry the recording environment's paths and
usernames; redacting them afterwards would break the verbatim rule, so the fix is
prevention. Sessions recorded on the Windows dev machine are **pipeline-validation
recordings**; the corpus for the preregistered run is recorded inside the Docker harness,
where paths and users are neutral by construction.
