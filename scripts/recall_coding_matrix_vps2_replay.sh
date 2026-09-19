#!/usr/bin/env bash
set -euo pipefail

# Run the five preregistered retrieval arms serially. The setup script owns the service restart,
# and the replay wrapper refuses any served variant mismatch before deleting or ingesting data.

readonly app_root="${1:?usage: recall_coding_matrix_vps2_replay.sh APP_ROOT APP_COMMIT OUTPUT_DIR}"
readonly app_commit="${2:?app commit is required}"
readonly output_dir="${3:?fresh output directory is required}"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"

if [[ -e "$output_dir" ]]; then
    echo "refusing to reuse a prior measurement directory" >&2
    exit 2
fi
if [[ ! -x "$setup_script" ]]; then
    echo "the committed VPS2 setup script is unavailable" >&2
    exit 2
fi

for variant in C0_raw_lexical C1_splade C2_procedure C3_rerank C4_task_pack; do
    "$setup_script" "$app_root" "$app_commit" "$variant"
    scripts/recall_experience_vps2_replay.sh "$variant" "$output_dir"
done

.venv/bin/python -m scripts.recall_coding_matrix_select \
    --input-dir "$output_dir" \
    --output "${output_dir}/selection.json"
sha256sum "$output_dir"/*.json "$output_dir"/*.service.log
