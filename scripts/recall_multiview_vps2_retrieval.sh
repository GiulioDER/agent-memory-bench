#!/usr/bin/env bash
set -euo pipefail

# Run the frozen three-arm grounded multiview retrieval screen in a fresh directory.

readonly recall_root="${1:?usage: recall_multiview_vps2_retrieval.sh RECALL_ROOT RECALL_COMMIT AMB_COMMIT OUTPUT_DIR RUN_ID ADMISSION_SELECTION}"
readonly recall_commit="${2:?RE-call commit is required}"
readonly amb_commit="${3:?AMB commit is required}"
readonly output_dir="${4:?output directory is required}"
readonly run_id="${5:?run id is required}"
readonly admission_selection="${6:?compiler admission selection is required}"
readonly amb_root="$(git rev-parse --show-toplevel)"
readonly protocol="${amb_root}/preregistration/092-recall-grounded-multiview-retrieval.md"
readonly runtime_env="${HOME}/.config/recall-aml/multiview-retrieval.env"
readonly service="recall-aml-experiment.service"
readonly base_url="http://127.0.0.1:18004"
readonly corpus_root="${amb_root}/corpus/conditions/${run_id}/present/seed-0"
readonly namespace="aml-multiview-${run_id}-present"

cd "$amb_root"

if [[ "$(git -C "$recall_root" rev-parse HEAD)" != "$recall_commit" ]]; then
    echo "RE-call checkout is not at the frozen commit" >&2
    exit 2
fi
if [[ "$(git -C "$amb_root" rev-parse HEAD)" != "$amb_commit" ]]; then
    echo "AMB checkout is not at the frozen commit" >&2
    exit 2
fi
if [[ ! -r "$protocol" ]] || ! grep -q '^Status: frozen ' "$protocol"; then
    echo "multiview preregistration is absent or still draft" >&2
    exit 2
fi
if [[ ! -r "$admission_selection" ]]; then
    echo "compiler admission selection is unavailable" >&2
    exit 2
fi
if [[ -e "$output_dir" || -e "$corpus_root" ]]; then
    echo "refusing to reuse multiview artifacts or condition corpus" >&2
    exit 2
fi
case "$output_dir" in
    */results/aml-grounded-multiview-retrieval/*) ;;
    *) echo "output directory is outside the frozen result root" >&2; exit 2 ;;
esac
if [[ ! "$run_id" =~ ^[a-z0-9][a-z0-9-]{5,80}$ ]]; then
    echo "run id is malformed" >&2
    exit 2
fi

"$amb_root/.venv/bin/python" - "$admission_selection" <<'PY'
import json
import sys

selection = json.load(open(sys.argv[1], encoding="utf-8"))
if (
    selection.get("selected_compiler") != "V2_anchor_raw"
    or selection.get("admission_pass") is not True
    or selection.get("authorize_m2_m3_retrieval") is not True
):
    raise SystemExit("compiler admission does not authorize M2 and M3 retrieval")
PY

mkdir -p -- "$output_dir"
cp --no-clobber -- "$admission_selection" "$output_dir/admission-selection.json"
"$amb_root/.venv/bin/python" -m scripts.assemble_condition_corpus \
    --condition present --seed 0 --out "$corpus_root"

run_variant() {
    local variant="$1"
    local artifact="${output_dir}/present-${variant}.json"
    local service_log="${output_dir}/present-${variant}.service.log"
    "$recall_root/scripts/aml_experience_vps2_setup.sh" \
        "$recall_root" "$recall_commit" "$variant"
    local api_key
    api_key="$(sed -n 's/^RECALL_AML_API_KEY=//p' "$runtime_env")"
    if [[ -z "$api_key" || "$api_key" == *$'\n'* || "$api_key" == *$'\r'* ]]; then
        echo "hosted API key is absent or malformed" >&2
        exit 2
    fi
    export AMB_RECALL_HOSTED_API_KEY="$api_key"
    local started_at
    started_at="$(date --iso-8601=seconds)"
    if ! "$amb_root/.venv/bin/python" -m scripts.recall_hosted_replay \
        --variant "$variant" \
        --base-url "$base_url" \
        --corpus "$corpus_root" \
        --tasks tasks \
        --output "$artifact" \
        --namespace "$namespace" \
        --captures 3; then
        journalctl --user -u "$service" --since "$started_at" -o cat --no-pager \
            >"$service_log"
        return 1
    fi
    journalctl --user -u "$service" --since "$started_at" -o cat --no-pager \
        >"$service_log"
}

run_variant M0_multiview_raw
run_variant M2_repository_raw
run_variant M3_experience_raw

"$amb_root/.venv/bin/python" -m scripts.recall_multiview_select \
    --artifacts-root "$output_dir" \
    --admission-selection "$output_dir/admission-selection.json" \
    --output "$output_dir/selection.json"

RECALL_COMMIT="$recall_commit" \
AMB_COMMIT="$amb_commit" \
RUN_ID="$run_id" \
AMB_ROOT="$amb_root" \
OUTPUT_PATH="$output_dir/identity.json" \
    "$amb_root/.venv/bin/python" - <<'PY'
import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["AMB_ROOT"])
output = Path(os.environ["OUTPUT_PATH"])
admission = output.parent / "admission-selection.json"
payload = {
    "schema_version": 1,
    "protocol": "preregistration/092-recall-grounded-multiview-retrieval.md",
    "run_id": os.environ["RUN_ID"],
    "recall_commit": os.environ["RECALL_COMMIT"],
    "amb_commit": os.environ["AMB_COMMIT"],
    "corpus_manifest_sha256": hashlib.sha256(
        (root / "corpus" / "manifest.json").read_bytes()
    ).hexdigest(),
    "preregistration_sha256": hashlib.sha256(
        (root / "preregistration" / "092-recall-grounded-multiview-retrieval.md").read_bytes()
    ).hexdigest(),
    "admission_selection_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

(
    cd "$output_dir"
    sha256sum \
        admission-selection.json \
        present-M0_multiview_raw.json present-M0_multiview_raw.service.log \
        present-M2_repository_raw.json present-M2_repository_raw.service.log \
        present-M3_experience_raw.json present-M3_experience_raw.service.log \
        selection.json identity.json >SHA256SUMS
)
cat "$output_dir/selection.json"
