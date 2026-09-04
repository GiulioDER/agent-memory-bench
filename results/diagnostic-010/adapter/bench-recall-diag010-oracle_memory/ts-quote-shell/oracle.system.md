Project memory:

[Evidence item]
That's the one. Decision: quote every path expansion in deploy.sh and in every deploy script. Prod hosts have spaces in directory names, and an unquoted variable goes through word splitting, so $TARGET must always appear as "$TARGET", and the same for every other path variable. Fix the script's existing lines as well, and treat an unquoted expansion in a deploy script as a review blocker.

Recorded: 2026-06-23
Status: current
Source: sessions/ts-quote-shell/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# shipit

`deploy.sh` stages the site into the release directory passed as its first argument:

    bash deploy.sh <release-dir>
