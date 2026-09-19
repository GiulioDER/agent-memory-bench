#!/usr/bin/env bash
set -euo pipefail

# Operational continuation only. It changes no replay behavior: wait for the detached E1 replay,
# verify its immutable artifact, switch the same hosted commit to E2, run the existing wrapper,
# and apply the preregistered mechanical selector. The bounded wait prevents a stuck provider run
# from silently holding the experiment forever.

readonly app_root="${1:?usage: recall_experience_vps2_finish.sh APP_ROOT APP_COMMIT OUTPUT_DIR}"
readonly app_commit="${2:?app commit is required}"
readonly output_dir="${3:?output directory is required}"
readonly e1_unit="recall-aml-e1-replay.service"
readonly setup_script="${app_root}/scripts/aml_experience_vps2_setup.sh"

for _ in $(seq 1 360); do
    if ! systemctl --user is-active --quiet "$e1_unit"; then
        break
    fi
    sleep 30
done
if systemctl --user is-active --quiet "$e1_unit"; then
    echo "E1 replay exceeded the three hour continuation bound" >&2
    exit 1
fi
if [[ ! -s "${output_dir}/E1_compiled.json" || ! -e "${output_dir}/E1_compiled.service.log" ]]; then
    echo "E1 replay ended without complete immutable artifacts" >&2
    exit 1
fi
if [[ ! -x "$setup_script" ]]; then
    echo "the committed VPS2 setup script is unavailable" >&2
    exit 2
fi

"$setup_script" "$app_root" "$app_commit" E2_compiled_raw
scripts/recall_experience_vps2_replay.sh E2_compiled_raw "$output_dir"
.venv/bin/python -m scripts.recall_experience_select \
    --input-dir "$output_dir" \
    --output "${output_dir}/selection.json"
sha256sum "${output_dir}/selection.json"
