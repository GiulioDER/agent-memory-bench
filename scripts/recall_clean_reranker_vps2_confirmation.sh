#!/usr/bin/env bash
set -euo pipefail

readonly app_root="${1:?usage: recall_clean_reranker_vps2_confirmation.sh APP_ROOT APP_COMMIT RUN_PREFIX RETRIEVAL_SELECTION SCREEN_SELECTION}"
readonly app_commit="${2:?app commit is required}"
readonly run_prefix="${3:?run prefix is required}"
readonly retrieval_selection="${4:?retrieval selection is required}"
readonly screen_selection="${5:?screen selection is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${HOME}/.config/recall-aml/clean-reranker.env"
readonly base_url="http://127.0.0.1:18004"
readonly conditions=(present absent superseded contradictory adjacent)

authorized="$(.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(int(d["confirmation_authorized"] and d["selected"]=="B1_raw_rerank"))' "$screen_selection")"
if [[ "$authorized" != "1" ]]; then
    echo "screen selected B0; confirmation is not authorized" >&2
    exit 3
fi
tasks="$(.venv/bin/python -c 'from harness.tasks import discover_tasks; print(",".join(sorted(t.task_id for t in discover_tasks() if t.task_id != "smoke-config-port")))')"
if [[ "$(awk -F, '{print NF}' <<<"$tasks")" != "34" ]]; then
    echo "confirmation task population drifted from 34" >&2
    exit 2
fi
export AMB_BLOCK_CONCURRENCY=3
export AMB_RECALL_HOSTED_URL="$base_url"

for condition in "${conditions[@]}"; do
    corpus_root="$(pwd)/corpus/conditions/${run_prefix}/${condition}/seed-0"
    if [[ -e "$corpus_root" ]]; then
        echo "refusing to reuse confirmation corpus ${corpus_root}" >&2
        exit 2
    fi
    .venv/bin/python -m scripts.assemble_condition_corpus \
        --condition "$condition" --seed 0 --out "$corpus_root"
    expected_hash="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["lineage"][sys.argv[2]]["corpus_sha256"])' "$retrieval_selection" "$condition")"
    namespace="amb-clean-${run_prefix}-${condition}"
    for variant in B0_raw B1_raw_rerank; do
        run_id="${run_prefix}-${condition}-${variant}"
        run_dir="results/${run_id}"
        if [[ -e "$run_dir" ]]; then
            echo "refusing to reuse confirmation run ${run_id}" >&2
            exit 2
        fi
        "$setup_script" "$app_root" "$app_commit" "$variant"
        api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
        export AMB_RECALL_HOSTED_API_KEY="$api_key"
        export AMB_RECALL_HOSTED_TRACE_PATH="$(pwd)/${run_dir}/search-trace.jsonl"
        export AMB_RECALL_HOSTED_EXPECTED_CORPUS_SHA256="$expected_hash"
        if [[ "$variant" == "B0_raw" ]]; then
            unset AMB_RECALL_HOSTED_REUSE_CORPUS
        else
            export AMB_RECALL_HOSTED_REUSE_CORPUS=1
        fi
        mkdir -p -- "$run_dir"
        curl --fail --silent --show-error "$base_url/version" >"${run_dir}/service-version.json"
        .venv/bin/python -m scripts.pilot \
            --run-id "$run_id" \
            --model deepseek/deepseek-v4-flash \
            --seeds 3 \
            --timeout 600 \
            --namespace "$namespace" \
            --memory-instruction protocol \
            --condition "$condition" \
            --corpus-root "$corpus_root" \
            --arms recall_hosted \
            --tasks "$tasks"
        curl --fail --silent --show-error \
            -H "Authorization: Bearer ${api_key}" -H 'Content-Type: application/json' \
            -d "{\"user_id\":\"${namespace}\"}" "$base_url/v1/corpus/status" \
            >"${run_dir}/corpus-status.json"
    done
done

.venv/bin/python -m scripts.recall_clean_reranker_confirmation_select \
    --results-root results \
    --run-prefix "$run_prefix" \
    --retrieval-selection "$retrieval_selection" \
    --screen-selection "$screen_selection" \
    --output "results/${run_prefix}-selection.json"
