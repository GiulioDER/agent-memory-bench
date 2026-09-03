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

## Qualifying smoke result

Run `smoke-supermemory-control-vps2-20260903-r6` completed on VPS2 on 2026-09-03. The roster was
exactly `bare,supermemory`, with the frozen model `deepseek/deepseek-v4-flash`, pinned Claude Code
2.1.259, Supermemory Claude Code plugin 0.1.6 at commit
`e6227edc4f33b83317cfde2e7cd9790c794d22d1`, and Supermemory Local server 0.0.8.

Both cells passed the executable checker: `RESULT.txt == '4731'`. Supermemory accepted 135 static
memory parts from 131 offered transcript files and `/v4/profile` returned seven verification hits.
`SessionStart` and `UserPromptSubmit` both exited 0 and each produced a nonempty output digest.
No cells were discarded. Smoke elapsed time was 356.2 seconds, and the recorded full-run
projection was 1,872.3 seconds, or 31.2 minutes. Both timing gates passed.

Artifacts: `results/smoke-supermemory-control-vps2-20260903-r6` on VPS2. This is a qualifying
smoke for the amended Supermemory Local explicit static memory treatment, not for the original
`/v3/documents` treatment that failed its VPS2 asynchronous extraction window.
