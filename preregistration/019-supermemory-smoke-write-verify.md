# 019: Supermemory smoke write and verify clarification

Status: FROZEN before measurement.

The previous reduced-roster smoke retries show that the Supermemory hook and ingest gates pass,
but the memory-heavy agent cell sometimes stops after reading the fixture without executing the
write. The smoke prompt now explicitly requires the existing task behavior: write the discovered
port with Bash to the relative `./RESULT.txt` in the current task sandbox, then verify it with Read.
The oracle value, checker, task fixture, arms, model, permissions, and full-run treatment are
unchanged.

The smoke is successful only if both `bare` and `supermemory` cells pass the checker, Supermemory
accepts the corpus with no discard, both required hooks exit zero with nonempty output digests, and
the 600 second smoke and 18,000 second projected full-run timing gates pass. The full run remains
only `bare` control and amended `supermemory`.

<!-- results are appended below this line -->
