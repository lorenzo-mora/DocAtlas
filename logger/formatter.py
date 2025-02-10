import json
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv

from utils import contains_placeholders


load_dotenv()
ENVIRONMENT = os.environ.get('ENV', "DEV")

class NDJsonFormatter(logging.Formatter):

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
            return json.dumps(log_record, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Handle serialization errors gracefully
            fallback_record = {
                'ts': self.formatTime(record, self.datefmt),
                'lvl': record.levelname,
                'msg': "Log serialization error",
                'stack_trace': str(e),
            }
            return json.dumps(fallback_record, ensure_ascii=False)

    def _create_log_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_record = {
            'ts': self.formatTime(record, self.datefmt),
            'lvl': record.levelname,
            'msg': record.getMessage(),
            'mod': record.module,
            'fn_name': record.funcName,
            'line_no': record.lineno,
            'path_name': record.pathname,
            'env': ENVIRONMENT
        }

        # Include stack trace if the log level is ERROR or EXCEPTION
        if record.levelname in ['ERROR', 'EXCEPTION'] and record.exc_info:
            log_record['stack_trace'] = self.formatException(record.exc_info)

        # Include extra fields if present
        if hasattr(record, 'extra') and isinstance(record.extra, dict):  # type: ignore
            log_record.update(record.extra)  # type: ignore

        # log_record.update(
        #     {k: v for k, v in record.__dict__.items() if k not in log_record})

        return log_record
