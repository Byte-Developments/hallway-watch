"""Web Push subscriptions and VAPID key management."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


def ensure_vapid_keys(keys_dir: Path) -> Vapid02:
    keys_dir.mkdir(parents=True, exist_ok=True)
    private_key = keys_dir / "private_key.pem"

    if private_key.exists():
        return Vapid02.from_file(str(private_key))

    vapid = Vapid02()
    vapid.generate_keys()
    vapid.save_key(str(private_key))
    logger.info("Generated new VAPID keys in %s", keys_dir)
    return vapid


def application_server_key(vapid: Vapid02) -> str:
    """URL-safe base64 public key for PushManager.subscribe({ applicationServerKey })."""
    raw_pub = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return b64urlencode(raw_pub)


class PushSubscriptionStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._subscriptions: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            if isinstance(data, list):
                for sub in data:
                    if isinstance(sub, dict) and "endpoint" in sub:
                        self._subscriptions[sub["endpoint"]] = sub
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load push subscriptions: %s", exc)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = list(self._subscriptions.values())
        self._path.write_text(json.dumps(payload, indent=2))

    def add(self, subscription: dict) -> None:
        endpoint = subscription.get("endpoint")
        if not endpoint:
            raise ValueError("Subscription missing endpoint")

        with self._lock:
            self._subscriptions[endpoint] = subscription
            self._save()

    def remove(self, endpoint: str) -> None:
        with self._lock:
            if endpoint in self._subscriptions:
                del self._subscriptions[endpoint]
                self._save()

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._subscriptions.values())


class PushNotifier:
    def __init__(
        self,
        vapid: Vapid02,
        store: PushSubscriptionStore,
        contact: str,
        private_key_path: Path,
    ) -> None:
        self._vapid = vapid
        self._store = store
        self._contact = contact
        self._private_key_path = private_key_path

    @property
    def public_key(self) -> str:
        return application_server_key(self._vapid)

    def add_subscription(self, subscription: dict) -> None:
        self._store.add(subscription)

    def send_all(self, title: str, message: str) -> int:
        payload = json.dumps({"title": title, "message": message})
        sent = 0

        for subscription in self._store.all():
            endpoint = subscription["endpoint"]
            try:
                webpush(
                    subscription_info=subscription,
                    data=payload,
                    vapid_private_key=str(self._private_key_path),
                    vapid_claims={"sub": self._contact},
                )
                sent += 1
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in (404, 410):
                    logger.info("Removing expired push subscription")
                    self._store.remove(endpoint)
                else:
                    logger.error("Web push failed: %s", exc)

        return sent
