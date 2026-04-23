from __future__ import annotations

import json
import logging
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


ALLOWED_LOGGER_PREFIXES = (
    "api",
    "mobguard",
    "mobguard_platform",
    "uvicorn.error",
)
BLOCKED_LOGGER_PREFIXES = (
    "uvicorn.access",
    "watchfiles",
)


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class SQLiteConsoleLogHandler(logging.Handler):
    def __init__(self, db_path: str | Path, *, service_name: str = "mobguard-api") -> None:
        super().__init__(level=logging.INFO)
        self.db_path = str(db_path)
        self.service_name = str(service_name or "mobguard-api").strip() or "mobguard-api"
        self._mobguard_console_handler = True

    def emit(self, record: logging.LogRecord) -> None:
        logger_name = str(record.name or "")
        if BLOCKED_LOGGER_PREFIXES and logger_name.startswith(BLOCKED_LOGGER_PREFIXES):
            return
        if ALLOWED_LOGGER_PREFIXES and not logger_name.startswith(ALLOWED_LOGGER_PREFIXES):
            return

        try:
            details: dict[str, Any] = {
                "pathname": str(getattr(record, "pathname", "") or ""),
                "lineno": int(getattr(record, "lineno", 0) or 0),
                "module": str(getattr(record, "module", "") or ""),
                "funcName": str(getattr(record, "funcName", "") or ""),
            }
            if record.exc_info:
                details["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()

            with sqlite3.connect(self.db_path, timeout=0.25) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA busy_timeout = 250")
                conn.execute(
                    """
                    INSERT INTO system_console_events (
                        service_name, logger_name, level, message, details_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.service_name,
                        logger_name,
                        str(record.levelname or "INFO").upper(),
                        record.getMessage(),
                        json.dumps(details, ensure_ascii=False),
                        _utcnow(),
                    ),
                )
                conn.commit()
        except Exception:
            return


def ensure_console_logging(db_path: str | Path, *, service_name: str = "mobguard-api") -> None:
    normalized_path = str(db_path)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if (
            getattr(handler, "_mobguard_console_handler", False)
            and getattr(handler, "db_path", None) == normalized_path
            and getattr(handler, "service_name", None) == service_name
        ):
            return
    root_logger.addHandler(SQLiteConsoleLogHandler(normalized_path, service_name=service_name))
    for logger_name in ("api", "mobguard", "mobguard_platform"):
        current_logger = logging.getLogger(logger_name)
        if current_logger.level in {logging.NOTSET, 0} or current_logger.level > logging.INFO:
            current_logger.setLevel(logging.INFO)
