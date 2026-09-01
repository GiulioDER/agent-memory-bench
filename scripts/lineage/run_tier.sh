#!/usr/bin/env bash
# Build one lineage tier's corpus, WITH the haystack.
#
# ⛔ AMB_HAYSTACK is the single switch that decides whether a run is comparable to official-002.
# Unset, `haystack_root()` returns None and assembles the 195-document standard feed, where
# `docs/RETRIEVAL_DIFFICULTY.md` measures voyage hit@10 = 1.000: retrieval is SATURATED and the
# run cannot separate "retrieved badly" from "never searched". official-002 ran with
# scale-25/seed-1 (verified from the live pilot's /proc environ). A first attempt at these tiers
# omitted it and built 207-document corpora against official-002's 4,911, which is why both were
# discarded. The path is amb-repo's because the haystack is gitignored and a git worktree does
# not carry it: checking that TRACKED files were intact is not checking that the corpus is.
#
# Asserts the tier reached the render BEFORE spending an embedding pass: a mis-set
# AMB_CORPUS_LINEAGE silently reproduces Tier 0 and would read as "lineage does not help".
set -euo pipefail
TIER="$1"; NS="$2"
REPO="$HOME/amb-lineage"; cd "$REPO"
set -a; . "$HOME/amb-secrets.env"; set +a
# The env file is NAMED, never hardcoded. This tree is public and .gitignore's first three
# lines forbid a remote path in it: an inventory of which machines exist and what runs on
# them is worth something with no credential attached. AMB_RECALL_REMOTE_ENV_FILE is the
# variable launch_official.sh already requires, so this adds no new configuration.
: "${AMB_RECALL_REMOTE_ENV_FILE:?set it in the secrets file; it holds VOYAGE_API_KEY}"
export VOYAGE_API_KEY=$(
  set -a; . "$AMB_RECALL_REMOTE_ENV_FILE"; set +a; printf '%s' "$VOYAGE_API_KEY"
)
export AMB_HAYSTACK="$HOME/amb-repo/corpus/haystack/scale-25/seed-1"
export AMB_CORPUS_LINEAGE="$TIER"
export PYTHONUNBUFFERED=1
PY="$HOME/amb-repo/.venv/bin/python"
[ -d "$AMB_HAYSTACK/synthetic" ] || { echo "AMB_HAYSTACK has no synthetic/: $AMB_HAYSTACK"; exit 2; }

echo "=== assembling superseded/seed-1 WITH haystack, asserting tier '$TIER' ==="
"$PY" - <<'PY'
import json, os, sys
from pathlib import Path
sys.path.insert(0, ".")
from harness.lineage import lineage_from_env
from scripts.abstention import selection_for
from scripts.assemble_condition_corpus import assemble, haystack_root

hs = haystack_root()
assert hs is not None, "haystack_root() returned None: AMB_HAYSTACK did not take effect"
root = Path("corpus/conditions/superseded/seed-1")
assemble("superseded", 1, selection_for("superseded"), root, haystack=hs)
man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
paths = [root / rel for rel in man["sessions"]]
fm = lineage_from_env(paths, root)
tier = os.environ["AMB_CORPUS_LINEAGE"]
n = len(paths)
sup = sum(1 for m in fm.values() if "supersedes" in m)
vu  = sum(1 for m in fm.values() if "valid_until" in m)
vf  = sum(1 for m in fm.values() if "valid_from" in m)
print("  sessions=%d tier=%s annotated=%d valid_from=%d valid_until=%d supersedes=%d"
      % (n, tier, len(fm), vf, vu, sup))
assert n > 4000, "only %d sessions: the haystack did NOT reach the corpus" % n
if tier == "none":
    assert (vf, vu, sup) == (0, 0, 0), "tier none produced frontmatter"
else:
    assert vf >= 207, "tier %s annotated only %d valid_from" % (tier, vf)
    want_pairs = 11 if tier == "declared" else 0
    assert (vu, sup) == (want_pairs, want_pairs), \
        "tier %s produced valid_until=%d supersedes=%d, expected %d each" % (tier, vu, sup, want_pairs)
print("  OK: haystack present and tier reaches the render")
PY

echo "=== building corpus for namespace $NS ==="
exec "$PY" -m scripts.prepare_recall_corpora --conditions superseded --namespace "$NS" --force
