#!/usr/bin/env bash
set -euo pipefail

readonly app_root="${1:?usage: recall_code_aware_vps2_robustness.sh APP_ROOT APP_COMMIT ARTIFACT_ID CONFIRMATION_SELECTION}"
readonly app_commit="${2:?app commit is required}"
readonly artifact_id="${3:?fresh robustness artifact id is required}"
readonly confirmation_selection="${4:?confirmation selection is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${HOME}/.config/recall-aml/code-aware.env"
readonly base_url="http://100.91.148.25:18004"
readonly artifact_root="$(pwd)/results/aml-code-aware-raw-v1/${artifact_id}"
readonly conditions=(present absent adjacent contradictory superseded)

if [[ -e "$artifact_root" ]]; then
    echo "refusing to reuse robustness artifacts" >&2
    exit 2
fi
authorized="$(.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(int(d["robustness_authorized"] and d["selected"]=="M1_code_neighbors"))' "$confirmation_selection")"
if [[ "$authorized" != "1" ]]; then
    echo "confirmation did not authorize robustness" >&2
    exit 3
fi
mkdir -p -- "$artifact_root"

for condition in "${conditions[@]}"; do
    corpus_root="$(pwd)/corpus/conditions/${artifact_id}/${condition}/seed-0"
    if [[ -e "$corpus_root" ]]; then
        echo "refusing to reuse robustness corpus" >&2
        exit 2
    fi
    .venv/bin/python -m scripts.assemble_condition_corpus \
        --condition "$condition" --seed 0 --out "$corpus_root"
    namespace="amb-code-${artifact_id}-${condition}"
    expected_hash=""
    for variant in M0_raw M1_code_neighbors; do
        artifact="${artifact_root}/${condition}-${variant}.json"
        service_log="${artifact_root}/${condition}-${variant}.service.log"
        reuse=()
        expected=()
        "$setup_script" "$app_root" "$app_commit" "$variant"
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
        journalctl --user -u recall-aml-experiment.service --since "$started_at" -o cat --no-pager \
            >"$service_log"
        if [[ "$variant" == "M0_raw" ]]; then
            expected_hash="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["corpus_status"]["corpus_sha256"])' "$artifact")"
        fi
    done
done

.venv/bin/python -m scripts.recall_code_aware_robustness_select \
    --artifact-root "$artifact_root" \
    --confirmation-selection "$confirmation_selection" \
    --output "${artifact_root}/selection.json"
sha256sum "$artifact_root"/*.json "$artifact_root"/*.service.log
