#!/usr/bin/env bash
set -euo pipefail

# Run one preregistered experience representation on VPS2 without exporting service secrets.

readonly variant="${1:?usage: recall_experience_vps2_replay.sh VARIANT OUTPUT_DIR}"
readonly output_dir="${2:?output directory is required}"
readonly runtime_env="${RECALL_AML_RUNTIME_ENV:-/home/sentiment/.config/recall-aml/experience-compiler.env}"
readonly service="recall-aml-experiment.service"

case "$variant" in
    E0_raw|E1_compiled|E2_compiled_raw) ;;
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
    --output "$artifact"
capture_service_log
trap - EXIT
sha256sum "$artifact" "$service_log"
