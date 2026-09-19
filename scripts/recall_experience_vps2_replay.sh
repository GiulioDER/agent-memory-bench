#!/usr/bin/env bash
set -euo pipefail

# Run one preregistered experience representation on VPS2 without exporting service secrets.

readonly variant="${1:?usage: recall_experience_vps2_replay.sh VARIANT OUTPUT_DIR}"
readonly output_dir="${2:?output directory is required}"
readonly resume_mode="${3:-}"
readonly service="recall-aml-experiment.service"
reuse_args=()
namespace_args=()
resume_args=()

case "$resume_mode" in
    "") ;;
    --resume-ingest)
        if [[ "$variant" != "C2_procedure" ]]; then
            echo "resume ingest is registered only for C2_procedure" >&2
            exit 2
        fi
        resume_args=(--resume-ingest)
        ;;
    *) echo "unsupported replay resume mode" >&2; exit 2 ;;
esac

case "$variant" in
    E0_raw|E1_compiled|E2_compiled_raw)
        readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/experience-compiler.env}"
        ;;
    V2_raw|V2_anchor_raw)
        readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/anchor-compiler-v2.env}"
        readonly anchor_namespace="${RECALL_ANCHOR_NAMESPACE:-}"
        if [[ -z "$anchor_namespace" ]]; then
            echo "RECALL_ANCHOR_NAMESPACE is required for compiler v2" >&2
            exit 2
        fi
        namespace_args=(--namespace "$anchor_namespace")
        ;;
    V3_raw|V3_anchor_raw)
        readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/anchor-compiler-v3.env}"
        readonly anchor_namespace="${RECALL_ANCHOR_NAMESPACE:-}"
        if [[ -z "$anchor_namespace" ]]; then
            echo "RECALL_ANCHOR_NAMESPACE is required for compiler v3" >&2
            exit 2
        fi
        namespace_args=(--namespace "$anchor_namespace")
        ;;
    M0_multiview_raw|M2_repository_raw|M3_experience_raw)
        readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/multiview-retrieval.env}"
        readonly multiview_namespace="${RECALL_MULTIVIEW_NAMESPACE:-}"
        if [[ -z "$multiview_namespace" ]]; then
            echo "RECALL_MULTIVIEW_NAMESPACE is required for the multiview retrieval screen" >&2
            exit 2
        fi
        namespace_args=(--namespace "$multiview_namespace")
        ;;
    C0_raw_lexical|C1_splade|C2_procedure|C3_rerank|C4_task_pack)
        readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-${HOME}/.config/recall-aml/coding-memory-matrix.env}"
        case "$variant" in
            C0_raw_lexical) namespace_args=(--namespace "aml-coding-raw-v1") ;;
            C1_splade)
                namespace_args=(--namespace "aml-coding-raw-v1")
                reuse_args=(--reuse-corpus)
                ;;
            C2_procedure) namespace_args=(--namespace "aml-coding-procedure-v1") ;;
            C3_rerank|C4_task_pack)
                namespace_args=(--namespace "aml-coding-procedure-v1")
                reuse_args=(--reuse-corpus)
                ;;
        esac
        ;;
    *) echo "unsupported experience variant" >&2; exit 2 ;;
esac
if [[ ! -r "$runtime_env" ]]; then
    echo "hosted runtime environment is unavailable" >&2
    exit 2
fi

# A systemd EnvironmentFile is not shell syntax. Read only the bearer key needed by the replay;
# DSN values may contain ampersands and must never be evaluated by this process.
api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
if [[ -z "$api_key" || "$api_key" == *$'\n'* || "$api_key" == *$'\r'* ]]; then
    echo "hosted API key is absent or malformed" >&2
    exit 2
fi
export AMB_RECALL_HOSTED_API_KEY="$api_key"

artifact="${output_dir}/${variant}.json"
service_log="${output_dir}/${variant}.service.log"
if [[ -e "$artifact" || -e "$service_log" ]]; then
    echo "refusing to overwrite an existing replay artifact" >&2
    exit 2
fi
mkdir -p -- "$output_dir"

served_variant="$(curl --fail --silent --show-error http://127.0.0.1:18004/version | \
    .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["variant"])')"
if [[ "$served_variant" != "$variant" ]]; then
    echo "served variant does not match requested replay" >&2
    exit 2
fi

started_at="$(date --iso-8601=seconds)"
capture_service_log() {
    journalctl --user -u "$service" --since "$started_at" -o cat --no-pager >"$service_log"
}
trap capture_service_log EXIT
.venv/bin/python -m scripts.recall_hosted_replay \
    --variant "$variant" \
    --base-url http://127.0.0.1:18004 \
    --corpus corpus \
    --tasks tasks \
    --output "$artifact" \
    "${namespace_args[@]}" \
    "${reuse_args[@]}" \
    "${resume_args[@]}"
capture_service_log
trap - EXIT
sha256sum "$artifact" "$service_log"
