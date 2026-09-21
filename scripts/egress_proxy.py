"""Minimal allowlist egress proxy for trusted brokers."""

from __future__ import annotations

import os
import selectors
import socket
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _allowed(host: str, allowlist: set[str]) -> bool:
    return host.lower().rstrip(".") in allowlist


class ProxyHandler(BaseHTTPRequestHandler):
    def _hosts(self) -> set[str]:
        return {
            item.strip().lower().rstrip(".")
            for item in os.environ.get("AMB_EGRESS_ALLOWED_HOSTS", "").split(",")
            if item.strip()
        }

    def do_CONNECT(self) -> None:
        host, separator, port_text = self.path.rpartition(":")
        if not separator or not host or not port_text.isdigit() or not _allowed(
            host, self._hosts()
        ):
            self.send_error(403, "destination is not allowlisted")
            return
        try:
            upstream = socket.create_connection((host, int(port_text)), timeout=15)
        except OSError:
            self.send_error(502, "allowlisted destination is unavailable")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.connection.setblocking(False)
        upstream.setblocking(False)
        selector = selectors.DefaultSelector()
        selector.register(self.connection, selectors.EVENT_READ, upstream)
        selector.register(upstream, selectors.EVENT_READ, self.connection)
        try:
            while True:
                events = selector.select(timeout=30)
                if not events:
                    break
                for key, _ in events:
                    source = key.fileobj
                    destination = key.data
                    if not isinstance(source, socket.socket) or not isinstance(
                        destination, socket.socket
                    ):
                        return
                    data = source.recv(64 * 1024)
                    if not data:
                        return
                    destination.sendall(data)
        except OSError:
            return
        finally:
            selector.close()
            upstream.close()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.scheme not in {"http", "https"} or not _allowed(
            parsed.hostname or "", self._hosts()
        ):
            self.send_error(403, "destination is not allowlisted")
            return
        if parsed.scheme != "http":
            self.send_error(405, "use CONNECT for HTTPS")
            return
        length = int(self.headers.get("Content-Length", "-1"))
        if length < 0 or length > 4 * 1024 * 1024:
            self.send_error(413, "request exceeds proxy limit")
            return
        body = self.rfile.read(length)
        try:
            connection = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=15)
            request_target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"proxy-authorization", "proxy-connection", "host"}
            }
            headers["Host"] = parsed.netloc
            request = (
                f"POST {request_target} HTTP/1.1\r\n"
                + "\r\n".join(f"{key}: {value}" for key, value in headers.items())
                + f"\r\nContent-Length: {len(body)}\r\n\r\n"
            ).encode("latin-1")
            connection.sendall(request + body)
            response = connection.recv(8 * 1024 * 1024 + 1)
            connection.close()
        except OSError:
            self.send_error(502, "allowlisted destination is unavailable")
            return
        self.connection.sendall(response)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> int:
    if not os.environ.get("AMB_EGRESS_ALLOWED_HOSTS"):
        raise SystemExit("egress allowlist is required")
    server = ThreadingHTTPServer(
        (
            os.environ.get("AMB_EGRESS_BIND_HOST", "0.0.0.0"),
            int(os.environ.get("AMB_EGRESS_PORT", "3128")),
        ),
        ProxyHandler,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
