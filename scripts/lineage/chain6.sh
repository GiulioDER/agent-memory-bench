#!/usr/bin/env bash
# Runs the reasoning diagnostic AFTER chain5's two grids, so nothing contends.
# Costs ~22 OpenRouter calls. Stops without spending anything if a prerequisite is missing.
set -uo pipefail
cd "$HOME/amb-lineage"
log(){ echo "[chain6 $(date -u +%H:%M:%SZ)] $*"; }
log "waiting for chain5"
while pgrep -f 'chain5.sh' >/dev/null; do sleep 60; done
log "chain5 done: $(tail -1 results/logs/chain5.log)"

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
export PYTHONPATH="$HOME/recall-553:$HOME/recall-553-deps"
export RECALL_REASONING_ANSWER_ENABLED=1
export RECALL_REASONING_ANSWER_PROVIDER=openai
export RECALL_REASONING_ANSWER_MODEL=deepseek/deepseek-v4-flash
export RECALL_REASONING_ANSWER_API_KEY="$OPENROUTER_API_KEY"
[ -n "${RECALL_REASONING_ANSWER_API_KEY:-}" ] || { log "no OpenRouter key"; exit 2; }
log "running the reasoning diagnostic"
"$HOME/amb-repo/.venv/bin/python" reasoning_diag.py > results/logs/reasoning-diag.log 2>&1
log "diagnostic exit $?  -> results/reasoning-diag.json"
