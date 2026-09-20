"""Environment configured entrypoint for a trusted broker container."""

from __future__ import annotations

import os

from .broker import (
    BrokerApplication,
    BrokerHTTPServer,
    BrokerPolicy,
    SignedCapabilityAuthority,
)
from .graphiti_broker import GraphitiMemoryHandler


def main() -> int:
    secret = os.environ.get("AMB_BROKER_SIGNING_SECRET", "").encode("utf-8")
    authority = SignedCapabilityAuthority(secret)
    service = os.environ.get("AMB_BROKER_SERVICE", "")
    run_id = os.environ.get("AMB_BROKER_RUN_ID", "")
    arm = os.environ.get("AMB_BROKER_ARM", "")
    namespace = os.environ.get("AMB_BROKER_NAMESPACE", "")
    upstream_url = os.environ.get("AMB_BROKER_UPSTREAM_URL", "")
    methods = tuple(
        item for item in os.environ.get("AMB_BROKER_METHODS", "").split(",") if item
    )
    memory_handler = (
        GraphitiMemoryHandler()
        if service == "memory" and os.environ.get("AMB_MEMORY_BACKEND") == "graphiti"
        else None
    )
    application = BrokerApplication(
        authority=authority,
        policy=BrokerPolicy(
            service=service,
            allowed_upstreams=tuple(
                item
                for item in os.environ.get("AMB_BROKER_UPSTREAM_ALLOWLIST", "").split(",")
                if item
            ),
            max_request_bytes=int(
                os.environ.get("AMB_BROKER_MAX_REQUEST_BYTES", str(4 * 1024 * 1024))
            ),
            ttl_s=float(os.environ.get("AMB_BROKER_TOKEN_TTL_S", "300")),
            network_policy_digest=os.environ.get("AMB_NETWORK_POLICY_DIGEST", ""),
        ),
        run_context={"run_id": run_id, "arm": arm, "namespace": namespace},
        upstream_url=upstream_url,
        upstream_credential=os.environ.get("AMB_BROKER_UPSTREAM_CREDENTIAL", ""),
        proxy_url=os.environ.get("AMB_EGRESS_PROXY_URL", ""),
        memory_handler=memory_handler,
    )
    if not service or not run_id or not arm or not namespace or not methods:
        raise SystemExit("broker scope and allowed methods are required")
    server = BrokerHTTPServer(
        (
            os.environ.get("AMB_BROKER_BIND_HOST", "0.0.0.0"),
            int(os.environ.get("AMB_BROKER_PORT", "8080")),
        ),
        application,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if memory_handler is not None:
            memory_handler.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
