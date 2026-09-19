#!/usr/bin/env bash
set -euo pipefail

readonly app_root="${1:?usage: recall_code_aware_vps2_retrieval.sh APP_ROOT APP_COMMIT OUTPUT_DIR RUN_TAG}"
readonly app_commit="${2:?app commit is required}"
readonly output_dir="${3:?fresh retrieval directory is required}"
readonly run_tag="${4:?run tag is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${HOME}/.config/recall-aml/code-aware.env"
readonly service="recall-aml-experiment.service"
readonly base_url="http://172.17.0.1:18004"
readonly corpus_root="$(pwd)/corpus/conditions/${run_tag}/present/seed-0"
readonly namespace="amb-code-${run_tag}-present"

if [[ -e "$output_dir" || -e "$corpus_root" ]]; then
    echo "refusing to reuse retrieval artifacts or condition corpus" >&2
    exit 2
fi
mkdir -p -- "$output_dir"

.venv/bin/python -m scripts.assemble_condition_corpus \
    --condition present --seed 0 --out "$corpus_root"

run_variant() {
    local variant="$1" expected_hash="${2:-}"
    local artifact="${output_dir}/present-${variant}.json"
    local service_log="${output_dir}/present-${variant}.service.log"
    local reuse=() expected=()
    "$setup_script" "$app_root" "$app_commit" "$variant"
    local api_key
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    if [[ -z "$api_key" ]]; then
        echo "hosted API key is unavailable" >&2
        exit 2
    fi
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    if [[ "$variant" == "M1_code_neighbors" ]]; then
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

run_variant M0_raw
corpus_hash="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["corpus_status"]["corpus_sha256"])' "${output_dir}/present-M0_raw.json")"
run_variant M1_code_neighbors "$corpus_hash"

.venv/bin/python -m scripts.recall_code_aware_select \
    --artifacts-root "$output_dir" \
    --output "${output_dir}/selection.json"
sha256sum "$output_dir"/*.json "$output_dir"/*.service.log
