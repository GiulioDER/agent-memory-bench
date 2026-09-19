#!/usr/bin/env bash
set -euo pipefail

readonly app_root="${1:?usage: recall_clean_reranker_vps2_screen.sh APP_ROOT APP_COMMIT RUN_PREFIX RETRIEVAL_SELECTION}"
readonly app_commit="${2:?app commit is required}"
readonly run_prefix="${3:?run prefix is required}"
readonly retrieval_selection="${4:?retrieval selection is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${HOME}/.config/recall-aml/clean-reranker.env"
readonly base_url="http://127.0.0.1:18004"
readonly tasks="xs-evolve-lease,xs-join-batch,xs-widen-manifest,fa-dedup-key,ts-mig-name,ts-semver-pin,ts-retry-cap,ts-config-layer,ts-atomic-write,ts-idempotent-run,ts-glob-hidden,ts-quote-shell"

authorized="$(.venv/bin/python -c 'import json,sys; print(int(json.load(open(sys.argv[1], encoding="utf-8"))["screen_authorized"]))' "$retrieval_selection")"
if [[ "$authorized" != "1" ]]; then
    echo "retrieval gates selected B0; executable screen is not authorized" >&2
    exit 3
fi

expected_hash="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["lineage"]["present"]["corpus_sha256"])' "$retrieval_selection")"
namespace="amb-clean-${run_prefix}-present"
export AMB_BLOCK_CONCURRENCY=3
export AMB_RECALL_HOSTED_URL="$base_url"

for variant in B0_raw B1_raw_rerank; do
    run_id="${run_prefix}-${variant}"
    run_dir="results/${run_id}"
    if [[ -e "$run_dir" ]]; then
        echo "refusing to reuse screen run ${run_id}" >&2
        exit 2
    fi
    "$setup_script" "$app_root" "$app_commit" "$variant"
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    export AMB_RECALL_HOSTED_TRACE_PATH="$(pwd)/${run_dir}/search-trace.jsonl"
    export AMB_RECALL_HOSTED_REUSE_CORPUS=1
    export AMB_RECALL_HOSTED_EXPECTED_CORPUS_SHA256="$expected_hash"
    mkdir -p -- "$run_dir"
    curl --fail --silent --show-error "$base_url/version" >"${run_dir}/service-version.json"
    .venv/bin/python -m scripts.pilot \
        --run-id "$run_id" \
        --model deepseek/deepseek-v4-flash \
        --seeds 3 \
        --timeout 600 \
        --namespace "$namespace" \
        --memory-instruction protocol \
        --condition present \
        --arms recall_hosted \
        --tasks "$tasks"
    curl --fail --silent --show-error \
        -H "Authorization: Bearer ${api_key}" -H 'Content-Type: application/json' \
        -d "{\"user_id\":\"${namespace}\"}" "$base_url/v1/corpus/status" \
        >"${run_dir}/corpus-status.json"
done

.venv/bin/python -m scripts.recall_clean_reranker_screen_select \
    --results-root results \
    --run-prefix "$run_prefix" \
    --retrieval-selection "$retrieval_selection" \
    --output "results/${run_prefix}-selection.json"
