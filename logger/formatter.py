import json
import logging
from typing import Any, Dict

from utils import contains_placeholders


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Format message with placeholders if present
        message = record.getMessage()
        if contains_placeholders(message):
            try:
                message = message % record.args
            except Exception as e:
                message = f"Message formatting error: {e}"
        record.msg = message

        # Create the structured log record
        log_record = self._create_log_record(record)

        # Serialize the log record to JSON
        try:
            return json.dumps(log_record)
        except (TypeError, ValueError) as e:
            # Handle serialization errors gracefully
            fallback_record = {
                'ts': self.formatTime(record, self.datefmt),
                'level': record.levelname,
                'message': "Log serialization error",
                'error': str(e),
            }
            return json.dumps(fallback_record)

    def _create_log_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_record = {
            'ts': self.formatTime(record, self.datefmt),
            'lvl': record.levelname,
            'msg': record.getMessage(),
            'mod': record.module,
            'fnName': record.funcName,
            'lineNo': record.lineno,
            'pathName': record.pathname
        }

        # Include extra fields if present
        if hasattr(record, 'extra') and isinstance(record.extra, dict): # type: ignore
            log_record.update(record.extra) # type: ignore

        # log_record.update(
        #     {k: v for k, v in record.__dict__.items() if k not in log_record})

        return log_record
