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
            sent_count = engine.process_pending(batch_size=50)
            if sent_count > 0:
                stats_after = engine.get_queue_stats()
                logger.info(
                    "WORKER cycle: sent=%d pending_before=%d pending_after=%d failed=%d",
                    sent_count,
                    stats_before["pending"],
                    stats_after["pending"],
                    stats_after["failed"],
                )
            else:
                pending = stats_before["pending"]
                if pending > 0:
                    logger.debug("WORKER cycle: 0 sent, %d still pending", pending)
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
