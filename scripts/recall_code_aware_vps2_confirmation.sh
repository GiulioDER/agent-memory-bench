#!/usr/bin/env bash
set -euo pipefail

readonly app_root="${1:?usage: recall_code_aware_vps2_confirmation.sh APP_ROOT APP_COMMIT ARTIFACT_ID RETRIEVAL_SELECTION SCREEN_SELECTION}"
readonly app_commit="${2:?app commit is required}"
readonly artifact_id="${3:?fresh confirmation artifact id is required}"
readonly retrieval_selection="${4:?retrieval selection is required}"
readonly screen_selection="${5:?screen selection is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${HOME}/.config/recall-aml/code-aware.env"
readonly base_url="http://100.91.148.25:18004"
readonly tasks="fa-dedup-key,ts-append-only,ts-atomic-write,ts-base36-id,ts-bom-merge,ts-bool-env,ts-casefold-sort,ts-cli-exitcode,ts-config-layer,ts-crlf-export,ts-csv-quote,ts-dedup-order,ts-empty-input,ts-glob-hidden,ts-golden-regen,ts-idempotent-run,ts-ignore-gen,ts-json-sorted,ts-legacy-hash,ts-log-mask,ts-manifest-rel,ts-mig-name,ts-natural-order,ts-nfc-count,ts-quote-shell,ts-retry-cap,ts-round-money,ts-schema-additive,ts-semver-pin,ts-stable-sort,ts-tz-utc,xs-evolve-lease,xs-join-batch,xs-widen-manifest"
readonly artifact_root="$(pwd)/results/aml-code-aware-raw-v1/${artifact_id}"

# shellcheck source=scripts/recall_code_aware_broker.sh
source "$(pwd)/scripts/recall_code_aware_broker.sh"
trap stop_code_aware_broker EXIT

if [[ -e "$artifact_root" ]]; then
    echo "refusing to reuse confirmation artifacts" >&2
    exit 2
fi
authorized="$(.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(int(d["confirmation_authorized"] and d["selected"]=="M1_code_neighbors"))' "$screen_selection")"
if [[ "$authorized" != "1" ]]; then
    echo "screen did not authorize confirmation" >&2
    exit 3
fi
expected_hash="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["lineage"]["corpus_sha256"])' "$retrieval_selection")"
namespace="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["lineage"]["namespace"])' "$retrieval_selection")"
export AMB_BLOCK_CONCURRENCY=3
# The VPS2 EnvironmentFile still carries a legacy bare image hash. The
# adjudicated agent identity is already required and fully qualified.
export AMB_PARTICIPANT_IMAGE_DIGEST="${AMB_PARTICIPANT_AGENT_DIGEST:?participant agent digest is required}"
export AMB_RECALL_HOSTED_URL="$base_url"
export AMB_RECALL_HOSTED_REUSE_CORPUS=1
export AMB_RECALL_HOSTED_EXPECTED_CORPUS_SHA256="$expected_hash"

for variant in M0_raw M1_code_neighbors; do
    run_id="aml-code-aware-raw-v1/${artifact_id}/${variant}"
    run_dir="$(pwd)/results/${run_id}"
    "$setup_script" "$app_root" "$app_commit" "$variant"
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    if [[ -z "$api_key" ]]; then
        echo "hosted API key is unavailable" >&2
        exit 2
    fi
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    export AMB_RECALL_HOSTED_TRACE_PATH="${run_dir}/search-trace.jsonl"
    mkdir -p -- "$run_dir"
    start_code_aware_broker "$run_dir" "$artifact_id" "$variant"
    started_at="$(date --iso-8601=seconds)"
    curl --fail --silent --show-error "$base_url/version" >"${run_dir}/service-version.json"
    .venv/bin/python -m scripts.pilot \
        --run-id "$run_id" \
        --model deepseek/deepseek-v4-flash \
        --seeds 3 \
        --timeout 600 \
        --price-in 0.0574 \
        --price-out 0.1148 \
        --price-as-of 2026-08-22 \
        --namespace "$namespace" \
        --memory-instruction protocol \
        --condition present \
        --arms recall_hosted \
        --tasks "$tasks"
    stop_code_aware_broker
    curl --fail --silent --show-error \
        -H "Authorization: Bearer ${api_key}" -H 'Content-Type: application/json' \
        -d "{\"user_id\":\"${namespace}\"}" "$base_url/v1/corpus/status" \
        >"${run_dir}/corpus-status.json"
    journalctl --user -u recall-aml-experiment.service --since "$started_at" -o cat --no-pager \
        >"${run_dir}/service.log"
done

.venv/bin/python -m scripts.recall_code_aware_confirmation_select \
    --artifact-root "$artifact_root" \
    --retrieval-selection "$retrieval_selection" \
    --screen-selection "$screen_selection" \
    --output "${artifact_root}/selection.json"
sha256sum "$artifact_root"/*.json "$artifact_root"/*/*.json "$artifact_root"/*/*.jsonl "$artifact_root"/*/*.log
