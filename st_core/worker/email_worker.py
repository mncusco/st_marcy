import logging
import time
import threading
from datetime import datetime, timezone

from database import SessionLocal
from services.email_engine import EmailEngine

logger = logging.getLogger("st_core.worker")

POLL_INTERVAL_SECONDS = 60
WORKER_NAME = "email_worker"


class EmailWorker:
    def __init__(self):
        self._stop_event = threading.Event()

    def process_cycle(self):
        db = SessionLocal()
        try:
            engine = EmailEngine(db)
            stats_before = engine.get_queue_stats()

            from models import EmailQueue, EmailStatus
            from datetime import datetime, timezone, timedelta
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            sent_today = db.query(EmailQueue).filter(
                EmailQueue.email_type == "editorial_reactivation",
                EmailQueue.status == EmailStatus.SENT,
                EmailQueue.sent_at >= today_start,
            ).count()
            daily_limit = 90
            remaining = max(0, daily_limit - sent_today)
            batch = min(remaining, 50) if remaining > 0 else 0

            if remaining <= 0 and stats_before.get("pending", 0) > 0:
                logger.info("WORKER: daily limit reached (%d/%d), pausing campaign until tomorrow", daily_limit, daily_limit)

            sent_count = engine.process_pending(batch_size=batch) if batch > 0 else 0
            if sent_count > 0:
                stats_after = engine.get_queue_stats()
                logger.info(
                    "WORKER cycle: sent=%d pending_before=%d pending_after=%d failed=%d daily=%d/%d",
                    sent_count,
                    stats_before["pending"],
                    stats_after["pending"],
                    stats_after["failed"],
                    sent_today + sent_count,
                    daily_limit,
                )
            else:
                pending = stats_before["pending"]
                if pending > 0:
                    logger.debug("WORKER cycle: 0 sent, %d still pending (daily=%d/%d)", pending, sent_today, daily_limit)
        except Exception as e:
            logger.exception("WORKER cycle error: %s", e)
        finally:
            db.close()

    def run_forever(self):
        logger.info("WORKER started (poll=%ds)", POLL_INTERVAL_SECONDS)
        while not self._stop_event.is_set():
            self.process_cycle()
            self._stop_event.wait(POLL_INTERVAL_SECONDS)
        logger.info("WORKER stopped")

    def stop(self):
        self._stop_event.set()


_worker_instance: EmailWorker | None = None
_worker_thread: threading.Thread | None = None


def start_worker():
    global _worker_instance, _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        logger.warning("WORKER already running")
        return
    _worker_instance = EmailWorker()
    _worker_thread = threading.Thread(target=_worker_instance.run_forever, daemon=True, name=WORKER_NAME)
    _worker_thread.start()
    logger.info("WORKER thread started")


def stop_worker():
    global _worker_instance, _worker_thread
    if _worker_instance:
        _worker_instance.stop()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=10)
        logger.info("WORKER thread stopped")
    _worker_instance = None
    _worker_thread = None
