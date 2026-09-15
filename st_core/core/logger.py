import os
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


class ExtraLoggerAdapter(logging.LoggerAdapter):
    """Adapter che aggiunge extra_fields strutturati a ogni record."""

    def process(self, msg, kwargs):
        extra = kwargs.pop("extra", {})
        extra_fields = dict(getattr(self.extra, "extra_fields", {}) if not isinstance(self.extra, dict) else self.extra)
        extra_fields.update(extra.get("extra_fields", {}))
        kwargs["extra"] = {"extra_fields": extra_fields}
        return msg, kwargs


def setup_logging(log_dir: str = "./logs", level: int = logging.INFO):
    os.makedirs(log_dir, exist_ok=True)

    text_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    json_fmt = JsonFormatter()

    root = logging.getLogger()
    root.setLevel(level)

    for h in root.handlers[:]:
        root.removeHandler(h)

    console = logging.StreamHandler()
    console.setFormatter(text_fmt)
    console.setLevel(level)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "st_core.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(text_fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    structured_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "st_core_structured.jsonl"),
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    structured_handler.setFormatter(json_fmt)
    structured_handler.setLevel(level)
    root.addHandler(structured_handler)

    error_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "error.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setFormatter(text_fmt)
    error_handler.setLevel(logging.ERROR)
    root.addHandler(error_handler)

    return root
