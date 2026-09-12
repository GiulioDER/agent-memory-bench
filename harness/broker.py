"""Trusted model and memory broker primitives.

The broker is controller-side code. Participant processes see only an opaque capability and a
fixed endpoint. Upstream credentials are constructor state of the trusted broker and are never
included in capability records, responses, or participant configuration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.server
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass


class BrokerError(RuntimeError):
    """A capability or broker request was rejected."""


def probe_jsonrpc_endpoint(
    url: str,
    token: str,
    required_tools: tuple[str, ...] = (),
    *,
    probe_tool: str | None = None,
    probe_arguments: Mapping[str, object] | None = None,
    timeout_s: float = 30.0,
) -> list[str]:
    """Perform the broker-side MCP admission probe without launching a host process."""

    def call(request: dict[str, object]) -> dict[str, object]:
        body = json.dumps(request, separators=(",", ":")).encode("utf-8")
        request_obj = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request_obj, timeout=timeout_s) as response:
            payload = json.loads(response.read(4 * 1024 * 1024 + 1))
        if not isinstance(payload, dict) or "error" in payload:
            raise BrokerError("broker MCP probe returned an invalid response")
        return payload

    call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    response = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    raw_result = response.get("result")
    raw_tools = raw_result.get("tools") if isinstance(raw_result, dict) else None
    if not isinstance(raw_tools, list):
        raise BrokerError("broker MCP probe returned no tool list")
    names = [
        str(item.get("name"))
        for item in raw_tools
        if isinstance(item, dict) and item.get("name")
    ]
    missing = sorted(set(required_tools) - set(names))
    if missing:
        raise BrokerError(f"broker does not offer required tools: {missing}")
    if probe_tool is not None:
        call(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": probe_tool, "arguments": dict(probe_arguments or {})},
            }
        )
    return names


@dataclass(frozen=True)
class BrokerPolicy:
    service: str
    allowed_upstreams: tuple[str, ...] = ()
    max_request_bytes: int = 4 * 1024 * 1024
    ttl_s: float = 300.0
    network_policy_digest: str = ""

    def __post_init__(self) -> None:
        if not self.service.strip():
            raise ValueError("broker service must not be empty")
        if self.max_request_bytes <= 0 or self.ttl_s <= 0:
            raise ValueError("broker limits must be positive")


@dataclass(frozen=True)
class Capability:
    run_id: str
    arm: str
    namespace: str
    service: str
    allowed_methods: tuple[str, ...]
    expires_at: float


class CapabilityAuthority:
    """Issue and validate short-lived, scope-bound opaque capabilities."""

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._grants: dict[str, Capability] = {}

    def issue(
        self,
        *,
        run_id: str,
        arm: str,
        namespace: str,
        service: str,
        allowed_methods: tuple[str, ...],
        ttl_s: float,
    ) -> str:
        if ttl_s <= 0:
            raise ValueError("capability TTL must be positive")
        token = secrets.token_urlsafe(32)
        grant = Capability(
            run_id=run_id,
            arm=arm,
            namespace=namespace,
            service=service,
            allowed_methods=tuple(sorted(set(allowed_methods))),
            expires_at=self._clock() + ttl_s,
        )
        with self._lock:
            self._grants[self._fingerprint(token)] = grant
        return token

    def validate(
        self,
        token: str,
        *,
        run_id: str,
        arm: str,
        namespace: str,
        service: str,
        method: str,
        request_bytes: int,
        max_request_bytes: int,
    ) -> Capability:
        if not token or request_bytes < 0 or request_bytes > max_request_bytes:
            raise BrokerError("capability request is invalid")
        with self._lock:
            grant = self._grants.get(self._fingerprint(token))
        if grant is None or grant.expires_at <= self._clock():
            raise BrokerError("capability is expired or unknown")
        if (grant.run_id, grant.arm, grant.namespace, grant.service) != (
            run_id,
            arm,
            namespace,
            service,
        ):
            raise BrokerError("capability scope does not match this session")
        if method not in grant.allowed_methods:
            raise BrokerError("method is not allowed by this capability")
        return grant

    def revoke_run(self, run_id: str) -> None:
        with self._lock:
            self._grants = {
                key: grant for key, grant in self._grants.items() if grant.run_id != run_id
            }

    @staticmethod
    def _fingerprint(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SignedCapabilityAuthority:
    """Stateless broker-side validator for tokens issued by the trusted controller.

    The signing key is broker-only configuration. The token carries scope and expiry, but never
    carries an upstream credential. HMAC comparison is constant time and malformed tokens fail
    closed.
    """

    def __init__(self, secret: bytes) -> None:
        if len(secret) < 32:
            raise ValueError("broker signing secret must contain at least 32 bytes")
        self._secret = secret

    def issue(
        self,
        *,
        run_id: str,
        arm: str,
        namespace: str,
        service: str,
        allowed_methods: tuple[str, ...],
        ttl_s: float,
    ) -> str:
        payload = {
            "run_id": run_id,
            "arm": arm,
            "namespace": namespace,
            "service": service,
            "allowed_methods": sorted(set(allowed_methods)),
            "expires_at": time.time() + ttl_s,
        }
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest()
        return f"{encoded}.{_b64(signature)}"

    def validate(
        self,
        token: str,
        *,
        run_id: str,
        arm: str,
        namespace: str,
        service: str,
        method: str,
        request_bytes: int,
        max_request_bytes: int,
    ) -> Capability:
        try:
            encoded, signature_text = token.split(".", 1)
            expected = hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest()
            signature = _unb64(signature_text)
            if not hmac.compare_digest(expected, signature):
                raise BrokerError("capability signature is invalid")
            payload = json.loads(_unb64(encoded))
            grant = Capability(
                run_id=str(payload["run_id"]),
                arm=str(payload["arm"]),
                namespace=str(payload["namespace"]),
                service=str(payload["service"]),
                allowed_methods=tuple(str(item) for item in payload["allowed_methods"]),
                expires_at=float(payload["expires_at"]),
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise BrokerError("capability is malformed") from error
        if request_bytes < 0 or request_bytes > max_request_bytes:
            raise BrokerError("capability request is invalid")
        if grant.expires_at <= time.time():
            raise BrokerError("capability is expired or unknown")
        expected_scope = (run_id, arm, namespace, service)
        actual_scope = (grant.run_id, grant.arm, grant.namespace, grant.service)
        if any(
            expected != "*" and expected != actual
            for expected, actual in zip(expected_scope, actual_scope)
        ):
            raise BrokerError("capability scope does not match this session")
        if method not in grant.allowed_methods:
            raise BrokerError("method is not allowed by this capability")
        return grant


class SessionCapabilityIssuer:
    """Issue the short-lived capabilities for one controller-owned session.

    Brokers are long-lived services, so their signed validator accepts ``*`` for the run, arm and
    namespace context. The signed grant still carries the concrete scope, and the controller
    creates a fresh pair for every participant invocation. This keeps provider credentials in the
    broker while preventing a token from crossing cells or services.
    """

    MODEL_METHODS = ("messages",)
    MEMORY_METHODS = ("initialize", "tools/list", "tools/call")

    def __init__(self, secret: str | bytes, *, ttl_s: float = 3600.0) -> None:
        raw = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.authority = SignedCapabilityAuthority(raw)
        if ttl_s <= 0:
            raise ValueError("capability TTL must be positive")
        self.ttl_s = ttl_s

    def issue(
        self,
        *,
        run_id: str,
        arm: str,
        namespace: str,
        memory: bool,
    ) -> tuple[str, str | None]:
        model = self.authority.issue(
            run_id=run_id,
            arm=arm,
            namespace=namespace,
            service="model",
            allowed_methods=self.MODEL_METHODS,
            ttl_s=self.ttl_s,
        )
        memory_token = None
        if memory:
            memory_token = self.authority.issue(
                run_id=run_id,
                arm=arm,
                namespace=namespace,
                service="memory",
                allowed_methods=self.MEMORY_METHODS,
                ttl_s=self.ttl_s,
            )
        return model, memory_token


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass
class BrokerApplication:
    """Small HTTP application used by the model or memory broker process."""

    authority: CapabilityAuthority
    policy: BrokerPolicy
    run_context: Mapping[str, str]
    upstream_url: str
    upstream_credential: str = ""
    proxy_url: str = ""
    memory_handler: Callable[[dict[str, object], Capability], dict[str, object]] | None = None

    def handle(self, headers: Mapping[str, str], body: bytes) -> tuple[int, dict[str, object]]:
        try:
            request = json.loads(body)
            if not isinstance(request, dict):
                raise BrokerError("request must be a JSON object")
            grant = self._authorize(headers, request, len(body))
            if self.memory_handler is not None:
                return 200, self.memory_handler(request, grant)
            return 200, self._forward(request)
        except BrokerError as error:
            return 403, {"error": str(error)}
        except (ValueError, KeyError) as error:
            return 400, {"error": str(error)}
        except (OSError, urllib.error.URLError) as error:
            return 502, {"error": f"upstream unavailable: {type(error).__name__}"}

    def _authorize(
        self, headers: Mapping[str, str], request: dict[str, object], request_bytes: int
    ) -> Capability:
        scheme, _, token = headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer":
            raise BrokerError("bearer capability required")
        method = str(
            request.get("method")
            or str(headers.get("X-AMB-Path", "")).rstrip("/").rsplit("/", 1)[-1]
        )
        return self.authority.validate(
            token,
            run_id=self.run_context["run_id"],
            arm=self.run_context["arm"],
            namespace=self.run_context["namespace"],
            service=self.policy.service,
            method=method,
            request_bytes=request_bytes,
            max_request_bytes=self.policy.max_request_bytes,
        )

    def handle_raw(self, headers: Mapping[str, str], body: bytes) -> tuple[int, bytes, str]:
        """Forward model streaming responses without parsing an SSE body as JSON."""

        try:
            request = json.loads(body)
            if not isinstance(request, dict):
                raise BrokerError("request must be a JSON object")
            grant = self._authorize(headers, request, len(body))
            if self.memory_handler is not None:
                payload = self.memory_handler(request, grant)
                return 200, json.dumps(payload, separators=(",", ":")).encode(), "application/json"
            payload, content_type = self._forward_raw(request)
            return 200, payload, content_type
        except BrokerError as error:
            return 403, json.dumps({"error": str(error)}).encode(), "application/json"
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            return 400, json.dumps({"error": str(error)}).encode(), "application/json"
        except (OSError, urllib.error.URLError) as error:
            return 502, json.dumps({"error": f"upstream unavailable: {type(error).__name__}"}).encode(), "application/json"

    def _forward(self, request: dict[str, object]) -> dict[str, object]:
        if not self.upstream_url:
            raise BrokerError("broker has no configured upstream")
        if self.policy.allowed_upstreams and not any(
            self.upstream_url.startswith(prefix) for prefix in self.policy.allowed_upstreams
        ):
            raise BrokerError("upstream is outside the broker allowlist")
        parsed_url = urllib.parse.urlsplit(self.upstream_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise BrokerError("broker upstream URL is invalid")
        body = json.dumps(request, separators=(",", ":")).encode("utf-8")
        call = urllib.request.Request(
            self.upstream_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.upstream_credential}"} if self.upstream_credential else {}),
            },
            method="POST",
        )
        if not self.proxy_url:
            raise BrokerError("broker egress proxy is not configured")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
        )
        with opener.open(call, timeout=30) as response:
            payload = response.read(self.policy.max_request_bytes + 1)
        if len(payload) > self.policy.max_request_bytes:
            raise BrokerError("upstream response exceeds broker limit")
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise BrokerError("upstream response is not a JSON object")
        return parsed

    def _forward_raw(self, request: dict[str, object]) -> tuple[bytes, str]:
        if not self.upstream_url:
            raise BrokerError("broker has no configured upstream")
        if self.policy.allowed_upstreams and not any(
            self.upstream_url.startswith(prefix) for prefix in self.policy.allowed_upstreams
        ):
            raise BrokerError("upstream is outside the broker allowlist")
        body = json.dumps(request, separators=(",", ":")).encode("utf-8")
        call = urllib.request.Request(
            self.upstream_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.upstream_credential}"} if self.upstream_credential else {}),
            },
            method="POST",
        )
        if not self.proxy_url:
            raise BrokerError("broker egress proxy is not configured")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
        )
        with opener.open(call, timeout=30) as response:
            payload = response.read(self.policy.max_request_bytes + 1)
            content_type = response.headers.get("Content-Type", "application/octet-stream")
        if len(payload) > self.policy.max_request_bytes:
            raise BrokerError("upstream response exceeds broker limit")
        return payload, content_type


class _Handler(http.server.BaseHTTPRequestHandler):
    server: BrokerHTTPServer

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "-1"))
        if length < 0 or length > self.server.application.policy.max_request_bytes:
            self.send_error(413, "request exceeds broker limit")
            return
        body = self.rfile.read(length)
        request_headers = {str(key): str(value) for key, value in self.headers.items()}
        request_headers["X-AMB-Path"] = self.path
        status, encoded, content_type = self.server.application.handle_raw(request_headers, body)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class BrokerHTTPServer(http.server.ThreadingHTTPServer):
    """Threaded broker server with no request logging, preventing token leakage."""

    def __init__(self, address: tuple[str, int], application: BrokerApplication) -> None:
        self.application = application
        super().__init__(address, _Handler)


def public_capability_metadata(grant: Capability) -> dict[str, object]:
    """Return nonsecret provenance for a grant without exposing its token."""

    return {
        "service": grant.service,
        "run_id": grant.run_id,
        "arm": grant.arm,
        "namespace": grant.namespace,
        "allowed_methods": list(grant.allowed_methods),
        "expires_at": grant.expires_at,
    }
