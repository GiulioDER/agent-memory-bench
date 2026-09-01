#!/usr/bin/env bash
# Queue preregistration 025's `evidence` run behind whatever grid is live.
#
# Waits, VERIFIES, then launches. The verification is the point: a queued run that fires at 3am
# into a broken apparatus produces a clean plausible null and nobody is awake to notice. Every
# check below refuses rather than proceeding, and says which one refused.
#
# It does NOT use scripts/launch_official.sh: that launcher hardcodes the five-arm official roster
# and refuses a checkout under a home directory. This runs from a worktree and two arms.
set -uo pipefail

REPO="$HOME/amb-evidence"
PYBIN="$HOME/amb-repo/.venv/bin/python"
# evidence-tool-001 is BURNED and must never be reused: its first attempt discarded all 490 cells
# on a missing PATH, and the three conditions it wrote read as COMPLETE to
# scripts/archive_partial.py (admission.json present, zero admitted), so `--resume` would skip
# every one of them and the run would exit 1 again having spent nothing and explained nothing.
RUN_ID="${RUN_ID:-evidence-tool-002}"
NAMESPACE="bench-official-002"
CONDITIONS="${CONDITIONS:-superseded,present,contradictory}"
ARMS="bare,recall"
SEEDS=5
MODEL="deepseek/deepseek-v4-flash"
# The frozen protocol of preregistration 002, matching protocol-025 and official-002 so the
# baseline and the treatment are priced on one basis. `the-two-published-runs-were-priced-
# differently` is why this is passed rather than defaulted.
PRICE_IN=0.0574
PRICE_OUT=0.1148
PRICE_AS_OF=2026-08-22

LOGDIR="$REPO/results/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/queue-$RUN_ID.log"
log(){ echo "[queue $(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG"; }

log "queued: $RUN_ID, $CONDITIONS x $ARMS x ${SEEDS} seeds, namespace $NAMESPACE"

# ---------------------------------------------------------------- 1. wait for the live grid
# Matched on the RUNNER, not on a run id, so any grid started meanwhile also holds this back.
# `lineage-tier-result-t0-vs-t2` records the cost of not doing this: a second grid began
# rebuilding a corpus under a live run.
waited=0
while pgrep -f 'scripts\.(abstention|pilot)' >/dev/null 2>&1; do
  if [ $((waited % 600)) -eq 0 ]; then
    log "waiting: $(pgrep -fa 'scripts\.abstention' | head -1 | cut -c1-110)"
  fi
  sleep 60
  waited=$((waited + 60))
done
log "host clear after ${waited}s"

# Let the box settle: the run that just ended leaves claude processes and page cache behind.
sleep 60

# ---------------------------------------------------------------- 2. preconditions
set -a; . "$HOME/amb-secrets.env"; set +a
[ -n "${OPENROUTER_API_KEY:-}" ] || { log "REFUSE: OPENROUTER_API_KEY unset"; exit 2; }

# ⛔ The CLI is not on PATH in a non-interactive shell, and its absence is not an error the run
# reports as one: every session fails instantly, every cell is DISCARDED, and the grid ends in
# three minutes with `admitted cells 0` and $0 spent. That is what happened on the first attempt,
# 490 cells, and both arms discarded equally so it looked environmental rather than like a
# treatment defect, which it was.
#
# scripts/launch_official.sh exports this and then checks it. This script deliberately does not use
# that launcher (it hardcodes the five-arm roster and refuses a home-directory checkout), and the
# first version copied its REFUSALS while dropping its environment setup. The check below is the
# one that catches the export above going missing again.
export PATH="$HOME/.npm-global/bin:$PATH"
command -v claude >/dev/null || { log "REFUSE: claude is not on PATH"; exit 2; }
[ -x "$PYBIN" ] || { log "REFUSE: no bench venv python at $PYBIN"; exit 2; }
: "${AMB_RECALL_REMOTE_ENV_FILE:?}"
export AMB_HAYSTACK="$HOME/amb-repo/corpus/haystack/scale-25/seed-1"
[ -d "$AMB_HAYSTACK" ] || { log "REFUSE: no haystack at AMB_HAYSTACK"; exit 2; }
# `the-haystack-is-gitignored-and-a-worktree-loses-it`: 207-document corpora were built instead of
# 4,911 with every gate green. Count it rather than trusting that the path exists.
HAYSTACK_DOCS=$(find "$AMB_HAYSTACK" -name '*.jsonl' | wc -l)
log "haystack: $HAYSTACK_DOCS documents"
[ "$HAYSTACK_DOCS" -gt 4000 ] || { log "REFUSE: haystack has $HAYSTACK_DOCS docs, expected ~4900"; exit 2; }

CREDIT=$(curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" https://openrouter.ai/api/v1/credits \
  | "$PYBIN" -c 'import json,sys;d=json.load(sys.stdin)["data"];print(round(d["total_credits"]-d["total_usage"],2))' 2>/dev/null)
log "openrouter credit: \$${CREDIT:-unknown}"
case "$CREDIT" in
  ''|unknown) log "REFUSE: could not read credit" ; exit 2 ;;
esac
"$PYBIN" -c "import sys; sys.exit(0 if float('$CREDIT') >= 4.0 else 1)" \
  || { log "REFUSE: \$$CREDIT is under the \$4 reserve for a 490-session grid"; exit 2; }

LOAD=$(awk '{print $1}' /proc/loadavg)
log "load average: $LOAD"

cd "$REPO" || { log "REFUSE: no worktree at $REPO"; exit 2; }
log "commit: $(git rev-parse --short HEAD)  branch: $(git branch --show-current)"

# The run guard refuses a dirty preregistration directory; check it here so the refusal is
# readable rather than arriving 200 lines into a launch.
if ! git diff --quiet -- preregistration/ || [ -n "$(git status --porcelain -- preregistration/)" ]; then
  log "REFUSE: preregistration/ is dirty"; exit 2
fi

# ⛔ Refuse a run id that already has artifacts. `--resume` SKIPS a condition that wrote
# admission.json, and a condition that admitted zero cells wrote one just the same, so restarting
# into a burned id silently runs nothing and exits 1. archive_partial.py cannot clear it either:
# it refuses such a condition as COMPLETE, because zero-admitted and finished are the same shape
# on disk. Pick a fresh id instead; nothing is ever deleted.
for existing in "$REPO/results/$RUN_ID"-*; do
  [ -e "$existing" ] || continue
  log "REFUSE: $RUN_ID already has artifacts at $(basename "$existing")."
  log "  A run id is single-use here. Set RUN_ID to a fresh one and requeue."
  exit 2
done
if [ -d "/tmp/agent-memory-bench-work/$RUN_ID" ] || \
   compgen -G "/tmp/agent-memory-bench-work/$RUN_ID-*" >/dev/null 2>&1; then
  log "REFUSE: a work root for $RUN_ID survives; every cell whose sandbox is there would be"
  log "  DISCARDED rather than re-run. Move it aside or pick a fresh RUN_ID."
  exit 2
fi

# ---------------------------------------------------------------- 3. apparatus checks
log "apparatus check 1: rendered prompts"
"$PYBIN" - <<'PY' 2>&1 | tee -a "$LOG"
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from adapters.recall.adapter import RecallAdapter
from scripts.pilot import memory_instructions
out = {}
with tempfile.TemporaryDirectory() as tmp:
    static = Path(tmp) / "s.md"; static.write_text("# Project notes\n\nStatic.\n", encoding="utf-8")
    for v in ("protocol", "evidence"):
        a = RecallAdapter(Path(tmp) / v, static, instruction=memory_instructions(v, ("recall",))["recall"])
        out[v] = a._write_prompt(f"ns-{v}").read_text(encoding="utf-8")
p, e = out["protocol"], out["evidence"]
d = [i for i, (x, y) in enumerate(zip(p.splitlines(), e.splitlines())) if x != y]
ok = (p != e and "recall_evidence" in e and len(d) == 1
      and len(p.splitlines()) == len(e.splitlines()))
print(f"  differing lines: {len(d)}; evidence names recall_evidence: {'recall_evidence' in e}")
sys.exit(0 if ok else 1)
PY
[ "${PIPESTATUS[0]}" = "0" ] || { log "REFUSE: apparatus check 1 failed"; exit 3; }

log "apparatus check 3: does the evidence bundle withhold anything on THIS corpus?"
"$PYBIN" "$REPO/scripts/check_bundle_withholds.py" --namespace "$NAMESPACE-superseded" 2>&1 | tee -a "$LOG"
RC="${PIPESTATUS[0]}"
case "$RC" in
  0) log "apparatus check 3 passed" ;;
  4) log "REFUSE: the evidence bundle withholds nothing on this corpus."
     log "  Amendment 1 registers this as the CANCEL condition: with no lineage the only filter"
     log "  is low_confidence, so the evidence arm would be the protocol arm and every endpoint"
     log "  would be uninterpretable. Nothing was spent."
     exit 4 ;;
  5) log "REFUSE: the checker could not find the bundle's item field, so every bundle parsed"
     log "  as empty and looked maximally withheld. That is a PARSE ERROR, not a result, and it"
     log "  is the one failure that would have spent the run. Fix bundle_items() and requeue."
     exit 5 ;;
  *) log "REFUSE: apparatus check 3 could not run (rc=$RC)"; exit 3 ;;
esac

# ---------------------------------------------------------------- 4. launch
ARGV=("$PYBIN" -m scripts.abstention
      --run-id "$RUN_ID" --namespace "$NAMESPACE" --conditions "$CONDITIONS"
      --arms "$ARMS" --seeds "$SEEDS" --model "$MODEL"
      --memory-instruction evidence --resume
      --price-in "$PRICE_IN" --price-out "$PRICE_OUT" --price-as-of "$PRICE_AS_OF")

RUNLOG="$LOGDIR/$RUN_ID-$(date -u +%Y%m%dT%H%M%SZ).log"
log "launching -> $RUNLOG"
printf -v QUOTED '%q ' "${ARGV[@]}"
systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 -p CPUQuota=500% \
  --quiet nice -n 10 bash -c "$QUOTED" > "$RUNLOG" 2>&1
log "run exited $?"
