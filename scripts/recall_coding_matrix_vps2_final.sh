#!/usr/bin/env bash
set -euo pipefail

# Run the final present-condition confirmation over every executable task for C0 and the promoted
# screen candidate. The candidate name is read from the immutable screen selection artifact.

readonly app_root="${1:?usage: recall_coding_matrix_vps2_final.sh APP_ROOT APP_COMMIT RUN_PREFIX SCREEN_SELECTION}"
readonly app_commit="${2:?app commit is required}"
readonly run_prefix="${3:?run prefix is required}"
readonly screen_selection="${4:?screen selection artifact is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/coding-memory-matrix.env}"

candidate="$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["promoted_candidate"])' "$screen_selection")"
case "$candidate" in
    C1_splade|C2_procedure|C3_rerank|C4_task_pack) ;;
    *) echo "the screen did not promote a nonbaseline candidate" >&2; exit 2 ;;
esac
tasks="$(.venv/bin/python -c 'from harness.tasks import discover_tasks; print(",".join(sorted(t.task_id for t in discover_tasks() if t.task_id != "smoke-config-port")))')"
task_count="$(awk -F, '{print NF}' <<<"$tasks")"
if [[ "$task_count" != 34 ]]; then
    echo "the final executable task population drifted from 34" >&2
    exit 2
fi

for variant in C0_raw_lexical "$candidate"; do
    run_id="${run_prefix}-${variant}"
    if [[ -e "results/${run_id}" ]]; then
        echo "refusing to reuse run ${run_id}" >&2
        exit 2
    fi
    "$setup_script" "$app_root" "$app_commit" "$variant"
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    export AMB_RECALL_HOSTED_URL="http://127.0.0.1:18004"
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    if [[ "$variant" == "C0_raw_lexical" ]]; then
        namespace="amb-coding-final-raw-v1"
        unset AMB_RECALL_HOSTED_REUSE_CORPUS
    elif [[ "$variant" == "C1_splade" ]]; then
        namespace="amb-coding-final-raw-v1"
        export AMB_RECALL_HOSTED_REUSE_CORPUS=1
    else
        namespace="amb-coding-final-procedure-v1"
        unset AMB_RECALL_HOSTED_REUSE_CORPUS
    fi
    mkdir -p -- "results/${run_id}"
    curl --fail --silent --show-error "$AMB_RECALL_HOSTED_URL/version" \
        >"results/${run_id}/service-version.json"
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
done

.venv/bin/python -m scripts.recall_coding_final_select \
    --results-root results \
    --run-prefix "$run_prefix" \
    --candidate "$candidate" \
    --output "results/${run_prefix}-selection.json"
