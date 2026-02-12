from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from datetime import datetime, timezone
from threading import Thread


class HealthState:
    """Shared state for health monitoring.

    Tracks write activity and errors to determine service health.
    The service is considered healthy when no errors have occurred.
    A successful write resets the error count, allowing recovery
    from transient failures.
    """

    def __init__(self) -> None:
        self.last_write_time: datetime | None = None
        self.messages_written: int = 0
        self.dlq_messages: int = 0
        self.errors: int = 0

    def record_write(self, message_count: int) -> None:
        self.last_write_time = datetime.now(timezone.utc)
        self.messages_written += message_count
        self.errors = 0

    def record_dlq_write(self, message_count: int) -> None:
        self.dlq_messages += message_count

    def record_error(self) -> None:
        self.errors += 1

    def is_healthy(self) -> bool:
        return self.errors == 0

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "status": "healthy" if self.is_healthy() else "unhealthy",
            "last_write": self.last_write_time.isoformat() if self.last_write_time else None,
            "messages_written": self.messages_written,
            "dlq_messages": self.dlq_messages,
            "errors": self.errors,
        }


health_state = HealthState()


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self) -> None:
        if self.path == "/health":
            is_healthy = health_state.is_healthy()
            status_code = 200 if is_healthy else 503

            response = health_state.to_dict()

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress HTTP request logs


def start_health_server(port: int = 8080) -> None:
    """Start health endpoint HTTP server in a background daemon thread."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health endpoint started on port {port}")
