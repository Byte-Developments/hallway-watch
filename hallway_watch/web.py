"""Local web server — browser notifications via Web Push + service worker."""

from __future__ import annotations

import json
import logging
import queue
import ssl
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

from hallway_watch.push import PushNotifier, PushSubscriptionStore, ensure_vapid_keys

if TYPE_CHECKING:
    from hallway_watch.config import NotificationConfig

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path("data")


class AlertHub:
    """Broadcasts alert events to browsers connected over SSE (live page fallback)."""

    def __init__(self) -> None:
        self._clients: list[queue.Queue[str]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue[str]:
        client_queue: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._clients.append(client_queue)
        return client_queue

    def unsubscribe(self, client_queue: queue.Queue[str]) -> None:
        with self._lock:
            if client_queue in self._clients:
                self._clients.remove(client_queue)

    def broadcast(self, title: str, message: str) -> None:
        payload = json.dumps({"title": title, "message": message})
        with self._lock:
            clients = list(self._clients)
        for client_queue in clients:
            client_queue.put(payload)


class _Handler(BaseHTTPRequestHandler):
    hub: AlertHub
    push: PushNotifier
    static_dir: Path

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.debug("HTTP " + format, *args)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, body: str, content_type: str) -> None:
        self._send_bytes(status, body.encode("utf-8"), content_type)

    def _serve_static(
        self,
        filename: str,
        content_type: str,
        *,
        cache_control: str = "no-store",
    ) -> None:
        path = self.static_dir / filename
        if not path.exists():
            self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain")
            return
        self._send_bytes(
            HTTPStatus.OK,
            path.read_bytes(),
            content_type,
            cache_control=cache_control,
        )

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._serve_static("index.html", "text/html; charset=utf-8")
            return

        if self.path == "/sw.js":
            self._serve_static(
                "sw.js",
                "application/javascript; charset=utf-8",
                cache_control="no-cache, no-store, must-revalidate",
            )
            return

        if self.path == "/vapid-public-key":
            payload = json.dumps({"publicKey": self.push.public_key})
            self._send_text(HTTPStatus.OK, payload, "application/json")
            return

        if self.path == "/events":
            self._handle_events()
            return

        self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain")

    def do_POST(self) -> None:
        if self.path != "/subscribe":
            self._send_text(HTTPStatus.NOT_FOUND, "Not found", "text/plain")
            return

        try:
            subscription = self._read_json_body()
            self.push.add_subscription(subscription)
            logger.info("Registered push subscription")
            self._send_text(HTTPStatus.CREATED, "subscribed", "text/plain")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Bad subscription payload: %s", exc)
            self._send_text(HTTPStatus.BAD_REQUEST, "invalid subscription", "text/plain")

    def _handle_events(self) -> None:
        client_queue = self.hub.subscribe()
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            self.wfile.write(b": connected\n\n")
            self.wfile.flush()

            while True:
                try:
                    payload = client_queue.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue

                event = f"data: {payload}\n\n".encode("utf-8")
                self.wfile.write(event)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.hub.unsubscribe(client_queue)


class NotificationServer:
    def __init__(self, config: NotificationConfig) -> None:
        self._config = config
        self.hub = AlertHub()
        self._thread: threading.Thread | None = None
        self._httpd: ThreadingHTTPServer | None = None

        keys_dir = DATA_DIR / "vapid"
        private_key_path = keys_dir / "private_key.pem"
        vapid = ensure_vapid_keys(keys_dir)
        store = PushSubscriptionStore(DATA_DIR / "push_subscriptions.json")
        self.push = PushNotifier(vapid, store, config.vapid_contact, private_key_path)

    def start(self) -> None:
        handler = type(
            "HallwayWatchHandler",
            (_Handler,),
            {"hub": self.hub, "push": self.push, "static_dir": STATIC_DIR},
        )
        self._httpd = ThreadingHTTPServer(
            (self._config.host, self._config.port),
            handler,
        )

        if self._config.tls_enabled:
            cert_path = Path(self._config.tls_cert)
            key_path = Path(self._config.tls_key)
            if not cert_path.exists() or not key_path.exists():
                raise FileNotFoundError(
                    f"TLS enabled but cert/key not found: {cert_path}, {key_path}. "
                    "Run scripts/install.sh or generate certs manually."
                )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
            self._httpd.socket = context.wrap_socket(
                self._httpd.socket,
                server_side=True,
            )

        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="hallway-watch-web",
            daemon=True,
        )
        self._thread.start()

        scheme = "https" if self._config.tls_enabled else "http"
        host_label = self._config.host if self._config.host != "0.0.0.0" else "<pi-ip>"
        logger.info("Notification page: %s://%s:%d", scheme, host_label, self._config.port)

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def notify(self) -> None:
        title = self._config.title
        message = self._config.message
        pushed = self.push.send_all(title, message)
        self.hub.broadcast(title, message)
        logger.info(
            "Alert sent to %d push subscriber(s) and live page listeners",
            pushed,
        )
