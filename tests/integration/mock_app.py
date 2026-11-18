"""Isolated test-only mock application for T16 readiness and OpenAPI fixtures."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MockApplication:
    def __init__(
        self,
        openapi_document: dict[str, Any] | None = None,
        *,
        mode: str = "success",
    ) -> None:
        self.openapi_document = openapi_document or {
            "openapi": "3.1.0",
            "paths": {
                "/health": {
                    "get": {
                        "responses": {
                            "200": {"description": "OK"}
                        }
                    }
                }
            },
        }
        self.mode = mode
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                if owner.mode == "slow" and self.path == "/health":
                    owner._send(self, 503, {"status": "starting"})
                    return
                if owner.mode == "oversized" and self.path == "/openapi.json":
                    owner._send_bytes(
                        self,
                        200,
                        b"x" * (10 * 1024 * 1024 + 1),
                        "application/json",
                    )
                    return
                if owner.mode == "malformed" and self.path == "/openapi.json":
                    owner._send_bytes(
                        self,
                        200,
                        b"{malformed",
                        "application/json",
                    )
                    return
                if self.path in {"/health", "/openapi.json"}:
                    content = (
                        owner.openapi_document
                        if self.path == "/openapi.json"
                        else {"status": "ready"}
                    )
                    owner._send(self, 200, content)
                    return
                owner._send(self, 404, {"error": "Not Found"})

        self.handler = Handler

    @staticmethod
    def _send(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        MockApplication._send_bytes(
            handler,
            status,
            body,
            "application/json",
        )

    @staticmethod
    def _send_bytes(
        handler: BaseHTTPRequestHandler,
        status: int,
        body: bytes,
        content_type: str,
    ) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def start(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="api-doc-sync-mock",
            daemon=True,
        )
        self.thread.start()
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None


def start_mock_application(
    openapi_document: dict[str, Any] | None = None,
    *,
    mode: str = "success",
) -> tuple[MockApplication, str]:
    application = MockApplication(openapi_document, mode=mode)
    base_url = application.start()
    return application, base_url


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the test-only API OpenAPI fixture.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--mode",
        choices=["success", "slow", "malformed", "oversized"],
        default="success",
    )
    args = parser.parse_args()

    application = MockApplication(mode=args.mode)
    application.server = ThreadingHTTPServer(("127.0.0.1", args.port), application.handler)
    thread = threading.Thread(
        target=application.server.serve_forever,
        name="api-doc-sync-mock",
        daemon=False,
    )
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        application.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
