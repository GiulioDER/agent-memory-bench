#!/usr/bin/env bash

broker_container=""
broker_log=""

stop_code_aware_broker() {
    if [[ -n "$broker_container" ]] && docker container inspect "$broker_container" >/dev/null 2>&1; then
        docker logs "$broker_container" >"$broker_log" 2>&1 || true
        docker stop --time 10 "$broker_container" >/dev/null
    fi
    broker_container=""
    broker_log=""
}

start_code_aware_broker() {
    local broker_run_dir="$1" broker_artifact_id="$2" broker_variant="$3"
    local safe_id
    safe_id="$(printf '%s-%s' "$broker_artifact_id" "$broker_variant" | tr -c 'A-Za-z0-9_.-' '-')"
    broker_container="amb-code-aware-${safe_id}"
    broker_log="${broker_run_dir}/broker.log"
    if docker container inspect "$broker_container" >/dev/null 2>&1; then
        echo "refusing to replace existing broker ${broker_container}" >&2
        exit 2
    fi
    export RECALL_HOSTED_API_KEY="${AMB_RECALL_HOSTED_API_KEY:?hosted API key is required}"
    docker run --detach --rm \
        --name "$broker_container" \
        --user "$(id -u):$(id -g)" \
        --network "${AMB_BROKER_NETWORK:-amb-broker-net}" \
        --add-host host.docker.internal:host-gateway \
        --publish 127.0.0.1:18085:8080 \
        --volume "$(pwd):/app:ro" \
        --volume "${broker_run_dir}:/trace" \
        --workdir /app \
        --env AMB_BROKER_SIGNING_SECRET \
        --env AMB_BROKER_TOKEN_TTL_S \
        --env AMB_NETWORK_POLICY_DIGEST \
        --env RECALL_HOSTED_API_KEY \
        --env RECALL_HOSTED_URL=http://host.docker.internal:18004 \
        --env RECALL_HOSTED_TRACE_PATH=/trace/search-trace.jsonl \
        --env AMB_RECALL_HOSTED_BROKER_PORT=8080 \
        "${AMB_RUNNER_IMAGE_DIGEST:?runner image digest is required}" \
        python -m scripts.recall_hosted_broker >/dev/null
    for _ in $(seq 1 30); do
        if curl --silent --output /dev/null --request POST --data '{}' \
            http://127.0.0.1:18085/; then
            export AMB_MEMORY_BROKER_URL="http://${broker_container}:8080"
            export AMB_CONTROLLER_MEMORY_BROKER_URL="http://127.0.0.1:18085"
            return
        fi
        sleep 1
    done
    docker logs "$broker_container" >&2 || true
    echo "hosted memory broker did not become ready" >&2
    exit 1
}
