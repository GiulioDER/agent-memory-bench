"""Small Anthropic Messages proxy that makes OpenRouter routing deterministic.

Claude Code talks to this process through ``ANTHROPIC_BASE_URL``.  The gateway accepts the
Anthropic Messages request, validates the frozen benchmark model, replaces any caller supplied
provider policy with the configured policy, and streams the upstream response unchanged.

The gateway retries only pre-stream transient failures when explicitly configured. A request that
has begun streaming is never retried, and 429 responses remain visible to the benchmark.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_UPSTREAM = "https://openrouter.ai/api/v1/messages"
DEFAULT_PROVIDER_ORDER = ("deepinfra",)
MAX_BODY_BYTES = 12 * 1024 * 1024
RETRYABLE_HTTP_STATUSES = frozenset({502, 503, 504})
_SAFE_RESPONSE_HEADERS = {
    "content-type",
    "cache-control",
    "x-request-id",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
}


def parse_provider_order(value: str | None) -> tuple[str, ...]:
    """Parse a comma separated provider list and reject ambiguous empty values."""

    if value is None:
        return DEFAULT_PROVIDER_ORDER
    providers = tuple(item.strip() for item in value.split(",") if item.strip())
    if not providers:
        raise ValueError("provider order must contain at least one provider")
    if len(set(providers)) != len(providers):
        raise ValueError("provider order must not contain duplicates")
    return providers


def build_upstream_payload(
    request_body: bytes,
    *,
    model: str = DEFAULT_MODEL,
    provider_order: tuple[str, ...] = DEFAULT_PROVIDER_ORDER,
) -> bytes:
    """Validate and rewrite one request without exposing credentials or message text."""

    try:
        payload = json.loads(request_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("request body is not valid JSON") from error
    if not isinstance(payload, dict):
        raise TypeError("request body must be a JSON object")
    incoming_model = payload.get("model")
    if incoming_model != model:
        raise ValueError(f"model must be {model!r}, got {incoming_model!r}")
    rewritten = dict(payload)
    rewritten["provider"] = {
        "order": list(provider_order),
        "allow_fallbacks": False,
    }
    return json.dumps(rewritten, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _provider_from_probe(data: bytes) -> str | None:
    """Extract the first provider field from a bounded response probe for diagnostics."""

    match = re.search(rb'"provider"\s*:\s*"([^"\\]{1,160})"', data[:262144])
    return match.group(1).decode("utf-8", "replace") if match else None


def stream_has_terminal_event(data: bytes) -> bool:
    """Return whether a buffered Anthropic SSE response contains ``message_stop``."""

    return b"event: message_stop" in data or re.search(
        rb'"type"\s*:\s*"message_stop"', data
    ) is not None


def should_retry_upstream(status: int | None, attempt: int, max_attempts: int) -> bool:
    """Retry only a bounded pre-stream transient failure, never a rate limit."""

    return attempt < max_attempts and (status is None or status in RETRYABLE_HTTP_STATUSES)


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "AMBOpenRouterGateway/1.0"

    @property
    def gateway(self) -> GatewayServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: Any) -> None:
        self.gateway.logger.info("http " + format, *args)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if urllib.parse.urlsplit(self.path).path == "/healthz":
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "model": self.gateway.model,
                    "provider_order": list(self.gateway.provider_order),
                    "allow_fallbacks": False,
                    "retry_attempts": self.gateway.retry_attempts,
                    "retry_backoff_s": self.gateway.retry_backoff_s,
                },
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_HEAD(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path in {"/healthz", "/api/hello"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in {"/v1/messages", "/api/v1/messages"}:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "-1")
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid request size"})
            return
        body = self.rfile.read(length)
        try:
            upstream_body = build_upstream_payload(
                body,
                model=self.gateway.model,
                provider_order=self.gateway.provider_order,
            )
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        request = urllib.request.Request(
            self.gateway.upstream,
            data=upstream_body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.gateway.api_key}",
                "Content-Type": "application/json",
                "Accept": self.headers.get("Accept", "application/json"),
                "HTTP-Referer": "https://github.com/agent-memory-bench",
                "X-Title": "Agent Memory Benchmark",
            },
        )
        response = None
        for attempt in range(1, self.gateway.retry_attempts + 1):
            try:
                response = urllib.request.urlopen(request, timeout=self.gateway.timeout_s)
                break
            except urllib.error.HTTPError as error:
                error_body = error.read(MAX_BODY_BYTES)
                if should_retry_upstream(error.code, attempt, self.gateway.retry_attempts):
                    delay = self.gateway.retry_backoff_s * (2 ** (attempt - 1))
                    self.gateway.logger.warning(
                        "upstream transient status=%s attempt=%d/%d retry_in=%.1fs",
                        error.code,
                        attempt,
                        self.gateway.retry_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                self.gateway.logger.error(
                    "upstream status=%s provider=%s error_bytes=%d attempts=%d",
                    error.code,
                    _provider_from_probe(error_body),
                    len(error_body),
                    attempt,
                )
                self._relay_response(error, error_body)
                return
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if should_retry_upstream(None, attempt, self.gateway.retry_attempts):
                    delay = self.gateway.retry_backoff_s * (2 ** (attempt - 1))
                    self.gateway.logger.warning(
                        "upstream transport transient=%s attempt=%d/%d retry_in=%.1fs",
                        type(error).__name__,
                        attempt,
                        self.gateway.retry_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                self.gateway.logger.error(
                    "upstream transport error=%s attempts=%d",
                    type(error).__name__,
                    attempt,
                )
                self._json(HTTPStatus.BAD_GATEWAY, {"error": "upstream transport failure"})
                return

        if response is None:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": "upstream retry exhausted"})
            return

        probe = bytearray()
        terminal_tail = bytearray()
        terminal_event = False
        try:
            self.send_response(response.status)
            for header, value in response.headers.items():
                if header.lower() in _SAFE_RESPONSE_HEADERS:
                    self.send_header(header, value)
            self.end_headers()
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                if len(probe) < 262144:
                    probe.extend(chunk[: 262144 - len(probe)])
                self.wfile.write(chunk)
                self.wfile.flush()
                terminal_tail.extend(chunk)
                del terminal_tail[:-512]
                if stream_has_terminal_event(bytes(terminal_tail)):
                    terminal_event = True
                    break
        except (BrokenPipeError, ConnectionResetError):
            self.gateway.logger.warning("client disconnected during upstream stream")
        finally:
            response.close()
        self.gateway.logger.info(
            "upstream status=%s provider=%s streamed_probe_bytes=%d terminal_event=%s",
            response.status,
            _provider_from_probe(bytes(probe)),
            len(probe),
            terminal_event,
        )

    def _relay_response(self, response: Any, body: bytes) -> None:
        self.send_response(response.code)
        for header, value in response.headers.items():
            if header.lower() in _SAFE_RESPONSE_HEADERS:
                self.send_header(header, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        api_key: str,
        model: str,
        provider_order: tuple[str, ...],
        upstream: str,
        timeout_s: float,
        retry_attempts: int,
        retry_backoff_s: float,
        logger: logging.Logger,
    ) -> None:
        super().__init__(address, GatewayHandler)
        self.api_key = api_key
        self.model = model
        self.provider_order = provider_order
        self.upstream = upstream
        self.timeout_s = timeout_s
        self.retry_attempts = retry_attempts
        self.retry_backoff_s = retry_backoff_s
        self.logger = logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("AMB_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AMB_GATEWAY_PORT", "8787")))
    parser.add_argument("--model", default=os.environ.get("AMB_GATEWAY_MODEL", DEFAULT_MODEL))
    parser.add_argument("--upstream", default=os.environ.get("AMB_GATEWAY_UPSTREAM", DEFAULT_UPSTREAM))
    parser.add_argument(
        "--provider-order",
        default=os.environ.get("AMB_GATEWAY_PROVIDER_ORDER", ",".join(DEFAULT_PROVIDER_ORDER)),
    )
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("AMB_GATEWAY_TIMEOUT", "900")))
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=int(os.environ.get("AMB_GATEWAY_RETRY_ATTEMPTS", "1")),
        help="total pre-stream attempts; 1 disables retry and 429 is never retried",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=float(os.environ.get("AMB_GATEWAY_RETRY_BACKOFF", "20")),
        help="initial seconds between transient retries",
    )
    parser.add_argument("--log", default=os.environ.get("AMB_GATEWAY_LOG"))
    args = parser.parse_args(argv)
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        parser.error("OPENROUTER_API_KEY is required")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.retry_attempts <= 0:
        parser.error("--retry-attempts must be positive")
    if args.retry_backoff < 0:
        parser.error("--retry-backoff must not be negative")
    try:
        provider_order = parse_provider_order(args.provider_order)
    except ValueError as error:
        parser.error(str(error))

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if args.log:
        handlers.append(logging.FileHandler(args.log, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
    logger = logging.getLogger("amb.gateway")
    server = GatewayServer(
        (args.host, args.port),
        api_key=api_key,
        model=args.model,
        provider_order=provider_order,
        upstream=args.upstream,
        timeout_s=args.timeout,
        retry_attempts=args.retry_attempts,
        retry_backoff_s=args.retry_backoff,
        logger=logger,
    )
    logger.info(
        "listening host=%s port=%d model=%s provider_order=%s allow_fallbacks=false",
        args.host,
        args.port,
        args.model,
        ",".join(provider_order),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
