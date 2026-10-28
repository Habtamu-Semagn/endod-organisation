"""The worker (``python -m app.worker``; the ``worker`` service in deploy/docker-compose.yml).

Every few seconds (ORG_WORKER_INTERVAL_SECONDS) it sends the integration
API's webhook deliveries that are due (app.integrations.webhooks), and every
ten minutes it deletes what is kept only for a while:

* the request log after 30 days;
* finished webhook deliveries (delivered or given up) after 30 days;
* used client assertions once they expire;
* Idempotency-Key answers after 24 hours.

It connects as the app role, like the API, and works across organisations in
the platform scope (app.db.platform_session). It needs only its database URL
and SESSION_SECRET (to open the sealed webhook secrets and event bodies):
never the key that signs access tokens.
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta
from typing import Optional

from sqlalchemy import delete

from app.config import get_settings
from app.db import check_connection_role, platform_session, utcnow
from app.integrations import webhooks
from app.models import (
    DeliveryStatus, IntegrationAssertion, IntegrationIdempotency, IntegrationRequest, WebhookDelivery,
)

logger = logging.getLogger("organisation.worker")

KEEP_LOGS_FOR = timedelta(days=30)
KEEP_IDEMPOTENCY_FOR = timedelta(hours=24)
CLEAN_EVERY = 600.0

_last_clean: Optional[float] = None
_stopping = False


def clean_up() -> int:
    """Deletes what has outlived its keeping time; returns how many rows went."""
    now = utcnow()
    with platform_session() as session:
        gone = session.execute(delete(IntegrationRequest).where(IntegrationRequest.at < now - KEEP_LOGS_FOR)).rowcount
        gone += session.execute(delete(WebhookDelivery).where(
            WebhookDelivery.status != DeliveryStatus.PENDING,
            WebhookDelivery.created_at < now - KEEP_LOGS_FOR)).rowcount
        gone += session.execute(delete(IntegrationAssertion).where(IntegrationAssertion.expires_at < now)).rowcount
        gone += session.execute(delete(IntegrationIdempotency).where(
            IntegrationIdempotency.created_at < now - KEEP_IDEMPOTENCY_FOR)).rowcount
    return gone or 0


def run_once(now: Optional[float] = None) -> int:
    """One round: the deliveries due, and the clean-up when it is time. Returns the work done."""
    global _last_clean
    now = time.monotonic() if now is None else now
    work = webhooks.deliver_due()
    if _last_clean is None or now - _last_clean >= CLEAN_EVERY:
        work += clean_up()
        _last_clean = now
    return work


def _stop(_signum, _frame) -> None:
    global _stopping
    _stopping = True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    check_connection_role()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("worker_started")
    while not _stopping:
        try:
            busy = run_once()
        except Exception:  # noqa: BLE001  (logged; the next round tries again)
            logger.exception("worker_round_failed")
            busy = 0
        if not busy:
            time.sleep(max(1, get_settings().ORG_WORKER_INTERVAL_SECONDS))


if __name__ == "__main__":
    main()
