# Why 2.4.1 took nine days to reach production

2026-05-01  a bounds bug is reported against textutils 2.4.0
2026-05-01  fix merged and released as textutils 2.4.1
2026-05-02  three consumer services are still on 2.4.0 and do not move
2026-05-06  someone notices; four pull requests are opened by hand
2026-05-10  the last of them merges

Nothing was broken by the fix. Nothing needed reviewing. The nine days
were spent editing a version string in four repositories, because the
reference pinned the patch component and nothing could move without a
human editing it.
