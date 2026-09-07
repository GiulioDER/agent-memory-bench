#!/usr/bin/env bash
# Run the full Claude-Mem additive AMB submission on VPS2.
#
# This launcher deliberately measures one new arm. The frozen official base is copied into the
# isolated worktree only so build_arm_submission.py can join the new result without rerunning or
# re-ingesting the base arms.
set -euo pipefail

REPO="${REPO:-$HOME/amb-claude-mem-official-001}"
BASE_REPO="${BASE_REPO:-$HOME/amb-repo}"
RUN_ID="${RUN_ID:-claude-mem-official-002}"
PY="${PY:-$BASE_REPO/.venv/bin/python}"
MODEL="${MODEL:-deepseek/deepseek-v4-flash}"
PRICE_IN="${PRICE_IN:-0.0574}"
PRICE_OUT="${PRICE_OUT:-0.1148}"
PRICE_AS_OF="${PRICE_AS_OF:-2026-08-22}"

export PATH="$HOME/.npm-global/bin:$HOME/.bun/bin:$PATH"
export CLAUDE_MEM_PLUGIN_DIR="${CLAUDE_MEM_PLUGIN_DIR:-$HOME/amb-claude-mem-v13-24-0/plugin}"
export AMB_BLOCK_CONCURRENCY="${AMB_BLOCK_CONCURRENCY:-4}"
export AMB_CORPUS_FLOOR="${AMB_CORPUS_FLOOR:-4000}"
export PYTHONUNBUFFERED=1

[[ -x "$PY" ]] || { echo "missing benchmark python: $PY" >&2; exit 2; }
[[ -x "$(command -v claude)" ]] || { echo "claude is not on PATH" >&2; exit 2; }
command -v bun >/dev/null || { echo "bun is not on PATH" >&2; exit 2; }
[[ -d "$CLAUDE_MEM_PLUGIN_DIR" ]] || { echo "missing CLAUDE_MEM_PLUGIN_DIR=$CLAUDE_MEM_PLUGIN_DIR" >&2; exit 2; }

mkdir -p "$REPO/results"

# Copy only the immutable base evidence needed by the additive join. The source checkout is left
# untouched; this worktree owns the new result directories.
if [[ ! -f "$REPO/results/official-003/leaderboard_summary.json" ]]; then
  mkdir -p "$REPO/results/official-003"
  cp "$BASE_REPO/results/official-003/leaderboard_summary.json" \
    "$REPO/results/official-003/leaderboard_summary.json"
fi
for condition in present absent superseded contradictory adjacent; do
  source_dir="$BASE_REPO/results/official-003-$condition"
  target_dir="$REPO/results/official-003-$condition"
  if [[ ! -f "$target_dir/records.final.jsonl" ]]; then
    mkdir -p "$target_dir"
    for name in records.final.jsonl admission.json costs.json; do
      cp "$source_dir/$name" "$target_dir/$name"
    done
  fi
done

run_condition() {
  local condition="$1"
  local tasks="$2"
  local corpus="$BASE_REPO/corpus/conditions/$condition/seed-1"
  [[ -f "$corpus/manifest.json" ]] || { echo "missing corpus manifest: $corpus" >&2; exit 2; }
  echo "[$condition] starting 27/11/10/10/11 frozen task selection with four workers" >&2
  "$PY" -m scripts.pilot \
    --run-id "$RUN_ID-$condition" \
    --arms claude_mem \
    --tasks "$tasks" \
    --seeds 5 \
    --model "$MODEL" \
    --namespace "$RUN_ID-$condition" \
    --corpus-root "$corpus" \
    --condition "$condition" \
    --memory-instruction protocol \
    --price-in "$PRICE_IN" \
    --price-out "$PRICE_OUT" \
    --price-as-of "$PRICE_AS_OF"
  "$PY" -m scripts.validate_run_setup \
    "$REPO/results/$RUN_ID-$condition" \
    --corpus-floor "$AMB_CORPUS_FLOOR" \
    --expect-arms claude_mem \
    --expect-instruction protocol
  "$PY" -m scripts.verify_run "$REPO/results/$RUN_ID-$condition"
}

run_condition present \
  "fa-dedup-key,ts-atomic-write,ts-base36-id,ts-bom-merge,ts-casefold-sort,ts-cli-exitcode,ts-config-layer,ts-crlf-export,ts-dedup-order,ts-empty-input,ts-golden-regen,ts-idempotent-run,ts-ignore-gen,ts-json-sorted,ts-legacy-hash,ts-log-mask,ts-manifest-rel,ts-mig-name,ts-natural-order,ts-nfc-count,ts-quote-shell,ts-retry-cap,ts-round-money,ts-schema-additive,ts-semver-pin,ts-stable-sort,ts-tz-utc"
run_condition absent \
  "ts-base36-id,ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc"
run_condition superseded \
  "ts-base36-id,ts-bom-merge,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc"
run_condition contradictory \
  "ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc"
run_condition adjacent \
  "ts-base36-id,ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc"

"$PY" scripts/build_arm_submission.py --write \
  --run-id "$RUN_ID" \
  --arm claude_mem \
  --base-run official-003 \
  --date "$(date -u +%F)" \
  --prereg preregistration/043-claude-mem-official-additive-hook-repair.md \
  --results-root "$REPO/results"
"$PY" scripts/build_arm_submission.py --check \
  --run-id "$RUN_ID" \
  --arm claude_mem \
  --base-run official-003 \
  --date "$(date -u +%F)" \
  --prereg preregistration/043-claude-mem-official-additive-hook-repair.md \
  --results-root "$REPO/results"
echo "FULL CLAUDE-MEM ADDITIVE RUN COMPLETE: $REPO/results/$RUN_ID/arm_summary.json" >&2
