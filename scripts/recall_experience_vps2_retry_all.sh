#!/usr/bin/env bash
set -euo pipefail

# Run the repaired transport envelope over all three arms in a fresh immutable directory. This is
# operational orchestration only; each arm still uses the committed replay and the frozen product.

readonly app_root="${1:?usage: recall_experience_vps2_retry_all.sh APP_ROOT APP_COMMIT OUTPUT_DIR}"
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

for variant in E0_raw E1_compiled E2_compiled_raw; do
    "$setup_script" "$app_root" "$app_commit" "$variant"
    scripts/recall_experience_vps2_replay.sh "$variant" "$output_dir"
done

.venv/bin/python -m scripts.recall_experience_select \
    --input-dir "$output_dir" \
    --output "${output_dir}/selection.json"
sha256sum \
    "${output_dir}/E0_raw.json" \
    "${output_dir}/E1_compiled.json" \
    "${output_dir}/E2_compiled_raw.json" \
    "${output_dir}/selection.json"
