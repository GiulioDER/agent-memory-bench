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

cd "$REPO"

# The key is read from a file this script does not create and never prints. It is deliberately
# outside the repository: the tree is shipped between hosts and published as artifacts.
if [ -f "$SECRETS" ]; then set -a; . "$SECRETS"; set +a; fi

export MEMPALACE_VENV="${MEMPALACE_VENV:-$HOME/mp-venv}"
export MEMPALACE_PALACE_ROOT="${MEMPALACE_PALACE_ROOT:-$HOME/mp}"
export RECALL_DSN="${RECALL_DSN:-postgresql:///?host=/home/sentiment/enterprise-rag-run/pgsock&port=55432&dbname=amb_bench}"
export PATH="$HOME/.npm-global/bin:$PATH"
export PYTHONUNBUFFERED=1

# Fail here rather than at the first cell. Each of these has cost a run somewhere.
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY is unset. Put it in $SECRETS" >&2; exit 2; }
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
      --memory-instruction skill --resume)
[ "${DRY_RUN:-0}" = "1" ] && ARGV+=(--dry-run)

echo "run id     : $RUN_ID"
echo "arms       : $ARMS"
echo "conditions : $CONDITIONS x $SEEDS seed(s)"
echo "commit     : $(git rev-parse --short HEAD)"
echo "log        : $LOG"

# setsid detaches; the scope bounds the whole tree. `nice` keeps the trading services ahead of
# this run whenever the CPU is contended, which it routinely is on this host.
setsid nohup bash -c "systemd-run --user --scope \
    -p MemoryMax=16G -p MemorySwapMax=0 -p CPUQuota=500% \
    --quiet nice -n 10 ${ARGV[*]}" > "$LOG" 2>&1 < /dev/null &

PID=$!
echo "$PID" > "$REPO/results/logs/$RUN_ID.pid"
sleep 2
echo ""
echo "launched detached, pid $PID"
echo "follow with : tail -f '$LOG'"
echo "stop with   : kill -- -$PID"
