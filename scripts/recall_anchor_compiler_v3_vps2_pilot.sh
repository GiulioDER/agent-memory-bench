#!/usr/bin/env bash
set -euo pipefail

# Run the frozen compiler v3 admission pilot in one fresh immutable directory.

readonly recall_root="${1:?usage: recall_anchor_compiler_v3_vps2_pilot.sh RECALL_ROOT RECALL_COMMIT AMB_COMMIT OUTPUT_DIR RUN_ID}"
readonly recall_commit="${2:?RE-call commit is required}"
readonly amb_commit="${3:?AMB commit is required}"
readonly output_dir="${4:?output directory is required}"
readonly run_id="${5:?run id is required}"
readonly amb_root="$(git rev-parse --show-toplevel)"
readonly runtime_env="${HOME}/.config/recall-aml/anchor-compiler-v3.env"
readonly table="recall_aml_anchor_compiler_v3_chunks"
readonly generation="aml-anchor-compiler-v3"

cd "$amb_root"

if [[ "$(git -C "$recall_root" rev-parse HEAD)" != "$recall_commit" ]]; then
    echo "RE-call checkout is not at the frozen commit" >&2
    exit 2
fi
if [[ "$(git -C "$amb_root" rev-parse HEAD)" != "$amb_commit" ]]; then
    echo "AMB checkout is not at the frozen commit" >&2
    exit 2
fi
if [[ -e "$output_dir" ]]; then
    echo "refusing to reuse compiler v3 result directory" >&2
    exit 2
fi
case "$output_dir" in
    */results/aml-anchor-compiler-v3/*) ;;
    *) echo "output directory is outside the frozen result root" >&2; exit 2 ;;
esac
if [[ ! "$run_id" =~ ^[a-z0-9][a-z0-9-]{5,80}$ ]]; then
    echo "run id is malformed" >&2
    exit 2
fi

mkdir -p -- "$output_dir"
readonly baseline_namespace="aml-anchor-v3-${run_id}-raw"
readonly candidate_namespace="aml-anchor-v3-${run_id}-candidate"

run_arm() {
    local variant="$1"
    local namespace="$2"
    "$recall_root/scripts/aml_experience_vps2_setup.sh" \
        "$recall_root" "$recall_commit" "$variant"
    RECALL_AML_RUNTIME_ENV="$runtime_env" \
    RECALL_ANCHOR_NAMESPACE="$namespace" \
        "$amb_root/scripts/recall_experience_vps2_replay.sh" "$variant" "$output_dir"
}

run_arm V3_raw "$baseline_namespace"
run_arm V3_anchor_raw "$candidate_namespace"

database_url="$(sed -n 's/^RECALL_AML_DATABASE_URL=//p' "$runtime_env")"
if [[ -z "$database_url" || "$database_url" == *$'\n'* || "$database_url" == *$'\r'* ]]; then
    echo "compiler v3 database setting is absent or malformed" >&2
    exit 2
fi
RECALL_AML_DATABASE_URL="$database_url" \
PYTHONPATH="$amb_root:$recall_root" \
    "$recall_root/.venv/bin/python" -m scripts.recall_anchor_compiler_audit \
    --corpus "$amb_root/corpus" \
    --namespace "$candidate_namespace" \
    --table "$table" \
    --generation "$generation" \
    --accepted-profile anchor-v3 \
    --output "$output_dir/anchor_audit.json"
unset database_url

"$amb_root/.venv/bin/python" -m scripts.recall_anchor_compiler_select \
    --baseline "$output_dir/V3_raw.json" \
    --candidate "$output_dir/V3_anchor_raw.json" \
    --audit "$output_dir/anchor_audit.json" \
    --baseline-variant V3_raw \
    --candidate-variant V3_anchor_raw \
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
payload = {
    "schema_version": 1,
    "protocol": "preregistration/094-recall-anchor-compiler-v3-admission.md",
    "run_id": os.environ["RUN_ID"],
    "recall_commit": os.environ["RECALL_COMMIT"],
    "amb_commit": os.environ["AMB_COMMIT"],
    "corpus_manifest_sha256": hashlib.sha256(
        (root / "corpus" / "manifest.json").read_bytes()
    ).hexdigest(),
    "preregistration_sha256": hashlib.sha256(
        (root / "preregistration" / "094-recall-anchor-compiler-v3-admission.md").read_bytes()
    ).hexdigest(),
}
Path(os.environ["OUTPUT_PATH"]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

(
    cd "$output_dir"
    sha256sum \
        V3_raw.json V3_raw.service.log \
        V3_anchor_raw.json V3_anchor_raw.service.log \
        anchor_audit.json selection.json identity.json >SHA256SUMS
)
cat "$output_dir/selection.json"
