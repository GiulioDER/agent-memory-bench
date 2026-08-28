# Pull request review friction, collected 2026-06-18

- PR 1204 touched only the README. config.json showed 31 changed lines.
- PR 1211 added a test. config.json showed 28 changed lines.
- PR 1216 reordered two lines in entries.txt with no semantic change.
  config.json showed 31 changed lines.
- PR 1220 genuinely changed a timeout. config.json showed 30 changed
  lines, one of which mattered.

Two reviewers have said they now skip the config.json hunk entirely.
That is the hunk where a real configuration change would appear.
