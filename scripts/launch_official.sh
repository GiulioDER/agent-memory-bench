#!/usr/bin/env bash
# Launch the official run ON VPS2, detached and bounded.
#
# Detached because an interruption anywhere else must not stop it: `abstention-002` lost 86
# sessions when the session that launched it ended. `setsid` puts the run in its own session so
# it survives the SSH connection closing, which `nohup` alone does not reliably do.
#
# Bounded because this host also runs live trading services. Two of the five arms do real local
# work here: MemPalace embeds every ingest and every query with onnxruntime, and five `claude`
# processes run concurrently within each cell. A cgroup limit is enforced by the KERNEL against
# the whole process tree, so the run is killed rather than the host.
#
# Resume is the default. A condition that wrote admission.json is skipped; one interrupted
# mid-flight is refused and must be archived first with scripts/archive_partial.py.
set -euo pipefail

REPO="${REPO:-$HOME/amb-repo}"
RUN_ID="${RUN_ID:-official-001}"
NAMESPACE="${NAMESPACE:-bench-official}"
CONDITIONS="${CONDITIONS:-absent,superseded,contradictory,adjacent}"
ARMS="${ARMS:-bare,placebo,claude_md,recall,mempalace}"
SEEDS="${SEEDS:-3}"
MODEL="${MODEL:-deepseek/deepseek-v4-flash}"
SECRETS="${SECRETS:-$HOME/amb-secrets.env}"

# Pricing is REQUIRED and deliberately not defaulted by the harness, because "a default is a price
# nobody chose": pilot-004 was priced at a stale default and its dollars were never comparable to
# pilot-003's. These are the frozen protocol of preregistration 002, and they are what the prior
# comparable runs used: results/abstention-001-absent/costs.json records pricing_as_of 2026-08-22.
# Matching them is the point, since this run keeps deepseek-v4-flash so its scores stay comparable.
# `--price-cache-read` is deliberately NOT passed, matching those runs: without it cache reads are
# charged at the fresh-input rate and the artifact says so.
PRICE_IN="${PRICE_IN:-0.0574}"
PRICE_OUT="${PRICE_OUT:-0.1148}"
PRICE_AS_OF="${PRICE_AS_OF:-2026-08-22}"

cd "$REPO"

# The key is read from a file this script does not create and never prints. It is deliberately
# outside the repository: the tree is shipped between hosts and published as artifacts.
if [ -f "$SECRETS" ]; then set -a; . "$SECRETS"; set +a; fi

export MEMPALACE_VENV="${MEMPALACE_VENV:-$HOME/mp-venv}"
export MEMPALACE_PALACE_ROOT="${MEMPALACE_PALACE_ROOT:-$HOME/mp}"
export PATH="$HOME/.npm-global/bin:$PATH"
export PYTHONUNBUFFERED=1

# Fail here rather than at the first cell. Each of these has cost a run somewhere.
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY is unset. Put it in $SECRETS" >&2; exit 2; }
# Where recall lives. Named, never stored: this tree is published with every run and a host
# inventory is disclosure on its own, per .gitignore's first three lines. A default here is
# what put a production .env path and another project's socket in a public artifact for a day.
REQUIRED_LOCATIONS="RECALL_DSN AMB_RECALL_REMOTE_ROOT AMB_RECALL_REMOTE_PYTHON AMB_RECALL_REMOTE_ENV_FILE"
# The ssh alias is needed only when the frozen config says the server is reached over ssh. Under
# `host` transport the harness runs ON the serving machine and never resolves one, so demanding it
# would refuse a correctly configured run over a variable it does not use.
if grep -q '"transport": *"ssh"' adapters/recall/config.frozen.json; then
  REQUIRED_LOCATIONS="$REQUIRED_LOCATIONS AMB_RECALL_SSH_HOST"
fi
for v in $REQUIRED_LOCATIONS; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || { echo "$v is unset. Put it in $SECRETS; see adapters/recall/location.example.env" >&2; exit 2; }
done
command -v claude >/dev/null || { echo "claude is not on PATH" >&2; exit 2; }
[ -x "$MEMPALACE_VENV/bin/python" ] || { echo "no MemPalace venv at $MEMPALACE_VENV" >&2; exit 2; }
[ -d "$MEMPALACE_PALACE_ROOT" ] || { echo "no palace root at $MEMPALACE_PALACE_ROOT" >&2; exit 2; }
[ -x "$REPO/.venv/bin/python" ] || { echo "no bench venv at $REPO/.venv" >&2; exit 2; }

mkdir -p "$REPO/results/logs"
STAMP="$(date -u +%Y%m%d-%H%M%SZ)"
LOG="$REPO/results/logs/$RUN_ID-$STAMP.log"

ARGV=(.venv/bin/python -m scripts.abstention
      --run-id "$RUN_ID" --namespace "$NAMESPACE" --conditions "$CONDITIONS"
      --arms "$ARMS" --seeds "$SEEDS" --model "$MODEL"
      --memory-instruction skill --resume
      --price-in "$PRICE_IN" --price-out "$PRICE_OUT" --price-as-of "$PRICE_AS_OF")
[ "${DRY_RUN:-0}" = "1" ] && ARGV+=(--dry-run)

echo "run id     : $RUN_ID"
echo "arms       : $ARMS"
echo "conditions : $CONDITIONS x $SEEDS seed(s)"
echo "commit     : $(git rev-parse --short HEAD)"
echo "pricing    : in $PRICE_IN / out $PRICE_OUT per Mtok, as of $PRICE_AS_OF"
echo "log        : $LOG"

# setsid detaches; the scope bounds the whole tree. `nice` keeps the trading services ahead of
# this run whenever the CPU is contended, which it routinely is on this host.
# Star form (joining the array with [*] rather than [@]) must never be used here: it flattens
# ARGV into ONE string, which the inner `bash -c` then
# word-splits and re-parses: with MODEL='deepseek; echo INJECTED >&2' the injected command
# runs, reproduced during the 2026-08-30 audit. RUN_ID, MODEL, CONDITIONS, ARMS and every
# price string are environment-overridable, so this needs no edit to the file to reach.
# printf %q re-quotes each element, so the second shell sees exactly the arguments this one
# built rather than a sentence it gets to interpret.
printf -v QUOTED_ARGV '%q ' "${ARGV[@]}"

setsid nohup bash -c "systemd-run --user --scope \
    -p MemoryMax=16G -p MemorySwapMax=0 -p CPUQuota=500% \
    --quiet nice -n 10 ${QUOTED_ARGV}" > "$LOG" 2>&1 < /dev/null &

PID=$!
echo "$PID" > "$REPO/results/logs/$RUN_ID.pid"
sleep 2

# ⚠️ Backgrounding reports nothing about whether the child SURVIVED. `systemd-run --user --scope`
# fails for want of a user session bus on a detached ssh login, and a missing price flag kills the
# run at argument validation in under a second; both leave this script printing a pid and an
# operator coming back to an empty log. The PowerShell twin checks this; for a while this one did
# not, which is the asymmetry tests/test_launchers.py exists to stop.
if ! kill -0 "$PID" 2>/dev/null; then
  echo "" >&2
  echo "THE RUN DID NOT START. The process exited within 2 seconds." >&2
  tail -20 "$LOG" >&2 2>/dev/null || true
  rm -f "$REPO/results/logs/$RUN_ID.pid"
  exit 1
fi

echo ""
echo "launched detached, pid $PID"
echo "follow with : tail -f '$LOG'"
echo "stop with   : kill -- -$PID"
