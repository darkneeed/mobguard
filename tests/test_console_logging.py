import logging
import shutil
import tempfile
import unittest
from pathlib import Path

from api.logging_console import SQLiteConsoleLogHandler
from mobguard_platform import AnalysisStore, PlatformStore


class ConsoleLoggingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-console-logging-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text('{"settings": {}}', encoding="utf-8")
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, {"settings": {}}, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_console_log_handler_writes_system_event(self):
        handler = SQLiteConsoleLogHandler(self.db_path, service_name="mobguard-api")
        logger = logging.getLogger("api.test_console_handler")
        previous_handlers = list(logger.handlers)
        previous_level = logger.level
        previous_propagate = logger.propagate
        try:
            logger.handlers = [handler]
            logger.setLevel(logging.INFO)
            logger.propagate = False
            logger.warning("Console handler test warning")
        finally:
            logger.handlers = previous_handlers
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate

        with self.store._connect() as conn:
            row = conn.execute(
                """
                SELECT service_name, logger_name, level, message
                FROM system_console_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["service_name"], "mobguard-api")
        self.assertEqual(row["logger_name"], "api.test_console_handler")
        self.assertEqual(row["level"], "WARNING")
        self.assertEqual(row["message"], "Console handler test warning")


if __name__ == "__main__":
    unittest.main()
