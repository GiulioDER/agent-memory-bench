#!/usr/bin/env bash
set -euo pipefail

# Run the frozen twelve-task executable screen serially over all five hosted configurations.

readonly app_root="${1:?usage: recall_coding_matrix_vps2_screen.sh APP_ROOT APP_COMMIT RUN_PREFIX}"
readonly app_commit="${2:?app commit is required}"
readonly run_prefix="${3:?run prefix is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"
readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/coding-memory-matrix.env}"
readonly tasks="xs-evolve-lease,xs-join-batch,xs-widen-manifest,fa-dedup-key,ts-mig-name,ts-semver-pin,ts-retry-cap,ts-config-layer,ts-atomic-write,ts-idempotent-run,ts-glob-hidden,ts-quote-shell"
readonly retrieval_selection="${RECALL_CODING_RETRIEVAL_SELECTION:?set RECALL_CODING_RETRIEVAL_SELECTION to selection.json}"

if [[ ! -x "$setup_script" ]]; then
    echo "the committed VPS2 setup script is unavailable" >&2
    exit 2
fi

for variant in C0_raw_lexical C1_splade C2_procedure C3_rerank C4_task_pack; do
    run_id="${run_prefix}-${variant}"
    if [[ -e "results/${run_id}" ]]; then
        echo "refusing to reuse run ${run_id}" >&2
        exit 2
    fi
    "$setup_script" "$app_root" "$app_commit" "$variant"
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    if [[ -z "$api_key" ]]; then
        echo "hosted API key is unavailable" >&2
        exit 2
    fi
    export AMB_RECALL_HOSTED_URL="http://127.0.0.1:18004"
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    case "$variant" in
        C0_raw_lexical)
            namespace="amb-coding-screen-raw-v1"
            unset AMB_RECALL_HOSTED_REUSE_CORPUS
            ;;
        C1_splade)
            namespace="amb-coding-screen-raw-v1"
            export AMB_RECALL_HOSTED_REUSE_CORPUS=1
            ;;
        C2_procedure)
            namespace="amb-coding-screen-procedure-v1"
            unset AMB_RECALL_HOSTED_REUSE_CORPUS
            ;;
        C3_rerank|C4_task_pack)
            namespace="amb-coding-screen-procedure-v1"
            export AMB_RECALL_HOSTED_REUSE_CORPUS=1
            ;;
    esac
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

.venv/bin/python -m scripts.recall_coding_screen_select \
    --results-root results \
    --run-prefix "$run_prefix" \
    --retrieval-selection "$retrieval_selection" \
    --output "results/${run_prefix}-selection.json"
