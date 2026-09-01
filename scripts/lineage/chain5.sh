#!/usr/bin/env bash
# t2 build (running) -> t0 build -> guard -> grid t0 -> grid t2. Stops at the first failure.
#
# ⛔ Every step exports AMB_HAYSTACK. It is the one switch that decides whether these tiers are
# comparable to official-002, it is not in the launcher or the secrets file, and omitting it once
# already cost two corpora and 94 sessions. The tenant builder and the grid must agree: if they
# disagree the tenants serve one corpus while the sessions run against another.
set -uo pipefail
REPO="$HOME/amb-repo"          # launch_official.sh hardcodes this; its logs and pid land there
cd "$HOME/amb-lineage"
log(){ echo "[chain5 $(date -u +%H:%M:%SZ)] $*"; }

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
[ ${#VOYAGE_API_KEY} -eq 46 ] || { log "voyage key wrong length"; exit 2; }

log "waiting for the t2 rebuild"
while pgrep -f 'prepare_recall_corpora .*bench-lineage-t2' >/dev/null; do sleep 30; done
grep -q "all requested conditions are built" results/logs/build-t2b.log || { log "t2 rebuild failed"; tail -20 results/logs/build-t2b.log; exit 1; }
log "t2 rebuilt"

log "building t0 with the haystack"
./run_tier.sh none bench-lineage-t0 > results/logs/build-t0b.log 2>&1 || { log "t0 build FAILED"; tail -20 results/logs/build-t0b.log; exit 1; }
grep -q "all requested conditions are built" results/logs/build-t0b.log || { log "t0 build incomplete"; exit 1; }
log "t0 rebuilt: $(grep -o 'corpus fingerprint .*' results/logs/build-t0b.log | head -1)"

log "guard on t2"
if ! "$HOME/amb-repo/.venv/bin/python" guard_t2.py bench-lineage-t2-superseded > results/logs/guard-t2b.log 2>&1; then
  log "GUARD FAILED, no grid will run"; tail -14 results/logs/guard-t2b.log; exit 1
fi
log "guard passed: $(grep -o 'verdicts=.*' results/logs/guard-t2b.log | head -1)"

for T in t0 t2; do
  RID="lineage-$T"
  log "launching grid $T"
  RUN_ID="$RID" NAMESPACE="bench-lineage-$T" CONDITIONS=superseded \
    ARMS=bare,recall SEEDS=5 AMB_BLOCK_CONCURRENCY=2 AMB_ALLOW_NAMED_PATHS=1 \
    AMB_HAYSTACK="$AMB_HAYSTACK" \
    bash scripts/launch_official.sh >> "results/logs/grid-$T-b.log" 2>&1
  sleep 30
  P=$(cat "$REPO/results/logs/$RID.pid" 2>/dev/null || echo "")
  [ -n "$P" ] || { log "no pid file for $T"; tail -15 "results/logs/grid-$T-b.log"; exit 1; }
  log "grid $T running as pid $P"
  while kill -0 "$P" 2>/dev/null; do sleep 60; done
  log "grid $T finished: $(wc -l < "$REPO/results/$RID-superseded/records.jsonl" 2>/dev/null || echo 0) records"
done
log "CHAIN COMPLETE"
