#!/usr/bin/env bash
set -euo pipefail

readonly app_root="${1:?usage: recall_clean_reranker_vps2_replay.sh APP_ROOT APP_COMMIT OUTPUT_DIR GRAPH_DIR RUN_TAG}"
readonly app_commit="${2:?app commit is required}"
readonly output_dir="${3:?fresh retrieval directory is required}"
readonly graph_dir="${4:?fresh graph directory is required}"
readonly run_tag="${5:?run tag is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${HOME}/.config/recall-aml/clean-reranker.env"
readonly service="recall-aml-experiment.service"
readonly base_url="http://127.0.0.1:18004"
readonly conditions=(present absent superseded contradictory adjacent)

if [[ -e "$output_dir" || -e "$graph_dir" ]]; then
    echo "refusing to reuse retrieval or graph artifacts" >&2
    exit 2
fi
mkdir -p -- "$output_dir" "$graph_dir"

run_variant() {
    local condition="$1" variant="$2" corpus_root="$3" namespace="$4" expected_hash="${5:-}"
    local artifact="${output_dir}/${condition}-${variant}.json"
    local service_log="${output_dir}/${condition}-${variant}.service.log"
    local reuse=() expected=()
    "$setup_script" "$app_root" "$app_commit" "$variant"
    local api_key
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    if [[ -z "$api_key" ]]; then
        echo "hosted API key is unavailable" >&2
        exit 2
    fi
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    if [[ "$variant" == "B1_raw_rerank" ]]; then
        reuse=(--reuse-corpus)
        expected=(--expected-corpus-sha256 "$expected_hash")
    fi
    local started_at
    started_at="$(date --iso-8601=seconds)"
    .venv/bin/python -m scripts.recall_hosted_replay \
        --variant "$variant" \
        --base-url "$base_url" \
        --corpus "$corpus_root" \
        --tasks tasks \
        --output "$artifact" \
        --namespace "$namespace" \
        --captures 3 \
        "${reuse[@]}" \
        "${expected[@]}"
    journalctl --user -u "$service" --since "$started_at" -o cat --no-pager >"$service_log"
}

for condition in "${conditions[@]}"; do
    corpus_root="$(pwd)/corpus/conditions/${run_tag}/${condition}/seed-0"
    if [[ -e "$corpus_root" ]]; then
        echo "refusing to reuse condition corpus ${corpus_root}" >&2
        exit 2
    fi
    .venv/bin/python -m scripts.assemble_condition_corpus \
        --condition "$condition" --seed 0 --out "$corpus_root"
    namespace="amb-clean-${run_tag}-${condition}"
    run_variant "$condition" B0_raw "$corpus_root" "$namespace"
    corpus_hash="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["corpus_status"]["corpus_sha256"])' "${output_dir}/${condition}-B0_raw.json")"
    if [[ "$condition" == "present" ]]; then
        .venv/bin/python -m scripts.recall_clean_graph_preflight \
            --corpus "$corpus_root" \
            --namespace "$namespace" \
            --base-url "$base_url" \
            --output "${graph_dir}/preflight.json"
    fi
    run_variant "$condition" B1_raw_rerank "$corpus_root" "$namespace" "$corpus_hash"
done

.venv/bin/python -m scripts.recall_clean_reranker_select \
    --artifacts-root "$output_dir" \
    --graph-preflight "${graph_dir}/preflight.json" \
    --output "${output_dir}/selection.json"
sha256sum "$graph_dir"/*.json "$output_dir"/*.json "$output_dir"/*.service.log
