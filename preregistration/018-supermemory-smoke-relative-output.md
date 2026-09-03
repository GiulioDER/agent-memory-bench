# 018: Supermemory smoke relative-output clarification

Status: FROZEN before measurement.

The reduced `bare,supermemory` smoke roster from preregistration 017 had three Supermemory cells
stop after reading the fixture without writing the checker artifact. One earlier smoke with the
same task succeeded, so this is an execution reliability issue rather than an adapter admission
result. The smoke prompt is clarified to name the current task sandbox and the relative path
`./RESULT.txt`. The task objective, oracle, arms, permissions, model, and checker are unchanged.

The next smoke remains successful only if both arms complete with the checker passing, Supermemory
accepts the corpus with no discard, both required hooks exit zero with nonempty output digests, and
the 600 second smoke and 18,000 second projected full-run timing gates pass. The full run remains
only `bare` control and amended `supermemory`.

<!-- results are appended below this line -->
