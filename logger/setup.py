import logging
import os
import queue
import sys
import threading
import time
from collections import defaultdict
from collections.abc import MutableMapping

from enum import Enum
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Any, Callable, Dict, Optional, Tuple, Union

from .formatter import JsonFormatter


class LogLevel(Enum):
    """
    Enumeration for log levels used in the application.

    This class defines the standard log levels that can be used
    throughout the codebase to categorize and filter log messages.
    """
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, level_str: str) -> 'LogLevel':
        if not level_str:
            raise ValueError("Log level string cannot be None or empty.")
        try:
            return cls[level_str.upper()]
        except KeyError:
            raise ValueError(f"Invalid log level string: {level_str}. "
                             f"Valid values are: {[level.name.lower() for level in cls]}")

    @classmethod
    def from_int(cls, level_int: int) -> 'LogLevel':
        if level_int < 0:
            raise ValueError("Log level must be a positive value. Instead, "
                             f"{level_int} was provided.")
        level_mapping = {
            10: LogLevel.DEBUG,
            20: LogLevel.INFO,
            30: LogLevel.WARNING,
            40: LogLevel.ERROR,
            50: LogLevel.CRITICAL
        }
        try:
            return level_mapping[level_int]
        except KeyError:
            raise ValueError(f"Invalid log level: {level_int}. "
                             f"Valid values are: {list(level_mapping.keys())}")

    def to_int(self) -> int:
        return list(LogLevel).index(self) + 1

    def to_logging_level(self) -> int:
        level_mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        return level_mapping[self]

    def next_level(self) -> Optional['LogLevel']:
        levels = list(LogLevel)
        index = levels.index(self)
        return levels[index + 1] if index < len(levels) - 1 else None

    def previous_level(self) -> Optional['LogLevel']:
        levels = list(LogLevel)
        index = levels.index(self)
        return levels[index - 1] if index > 0 else None

class InstanceAdapter(logging.LoggerAdapter):
    def __init__(
            self,
            logger: logging.Logger,
            extra: Optional[MutableMapping[str, Any]] = None
        ) -> None:
        if extra is None:
            extra = defaultdict(dict)
        elif not isinstance(extra, MutableMapping):
            raise ValueError("'extra' must be a mutable mapping.")

        super().__init__(logger, extra)
        self._lock = threading.Lock()

    def process(
            self,
            msg: str,
            kwargs: MutableMapping[str, Union[dict, Any]]
        ) -> Tuple[str, MutableMapping[str, Any]]:
        # Ensure 'extra' exists and is a MutableMapping
        extra: Dict[str, Any] = kwargs.setdefault("extra", {})
        if not isinstance(extra, MutableMapping):
            self.logger.error(f"Invalid 'extra' type: {type(extra)}")
            raise ValueError("'extra' must be a MutableMapping if provided "
                             "in logging kwargs.")

        # Merge the adapter's context ('self.extra') with the provided 'extra'
        kwargs["extra"] = {**self.extra, **extra} # type: ignore
        return msg, kwargs

    def add_context(self, key: str, value: Any) -> None:
        """Add or update context dynamically."""
        with self._lock:
            self.extra[key] = value # type: ignore

    def remove_context(self, key: str) -> None:
        """Remove a key from the context."""
        with self._lock:
            self.extra.pop(key, None) # type: ignore

class LoggerManager:
    """Class to manage logger configuration and operations."""

    formatted_message = '%(asctime)s | %(levelname)s :: %(message)s'

    def __init__(
        self,
        name: str,
        folder_path: str = "logs",
        max_size: int = 500 * 1024 * 1024,
        console_level: Union[LogLevel, str, int] = LogLevel.INFO,
        file_level: Union[LogLevel, str, int] = LogLevel.DEBUG
    ) -> None:
        self.name = name
        self.log_dir = folder_path
        self.max_size = max_size
        self.console_level = self._validate_log_level(console_level)
        self.file_level = self._validate_log_level(file_level)
        self.logger: Optional[logging.Logger] = None
        self.listener: Optional[QueueListener] = None

    @staticmethod
    def _validate_log_level(level: Union[LogLevel, str, int]) -> LogLevel:
        """Validate and convert a log level input to a LogLevel instance."""
        if isinstance(level, LogLevel):
            return level
        if isinstance(level, str):
            return LogLevel.from_string(level)
        if isinstance(level, int):
            return LogLevel.from_int(level)
        raise ValueError(
            f"Log level must be a string, integer, or LogLevel instance. Got: {type(level)}"
        )

    def setup_logger(self, force: bool = False) -> logging.Logger:
        """Set up the logger with specified configurations.

        Parameters
        ----------
        force : bool, optional
            If True, forces reconfiguration of the logger even if it is
            already set up. By default is False.
        """
        if self.logger is not None and not force:
            # Logger already exists, and force is False
            return self.logger

        if self.logger is not None and force:
            # Clear existing handlers
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
                handler.close()

        # Initialize logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        os.makedirs(self.log_dir, exist_ok=True)

        # Set up handlers
        self._setup_handlers()

        # Queue listener for asynchronous logging
        self._start_listener()

        return self.logger

    def _setup_handlers(self):
        """Set up console and file handlers for the logger."""
        timestamp = time.strftime('%Y%m%d')
        log_file = os.path.join(self.log_dir, f"{self.name}_{timestamp}.log")

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level.to_logging_level())
        console_handler.setFormatter(
            logging.Formatter(self.formatted_message)
        )

        # File handler with JSON formatter
        file_handler = RotatingFileHandler(
            log_file, maxBytes=self.max_size, backupCount=5
        )
        file_handler.setLevel(self.file_level.to_logging_level())
        file_handler.setFormatter(JsonFormatter())

        # Queue handler
        log_queue = queue.Queue(-1)
        queue_handler = QueueHandler(log_queue)
        if self.logger is None:
            raise RuntimeError("Logger setup failed, `logger` is None.")
        self.logger.addHandler(queue_handler)

        self.listener = QueueListener(
            log_queue, console_handler, file_handler, respect_handler_level=True
        )

    def _start_listener(self):
        """Start the queue listener."""
        if not self.listener:
            raise RuntimeError("Listener has not been initialized.")
        self.listener.start()
        import atexit

        atexit.register(self.listener.stop)

    def update_levels(
        self,
        console_level: Union[LogLevel, str, int],
        file_level: Union[LogLevel, str, int],
    ):
        """Update log levels for console and file handlers."""
        if self.logger is None:
            raise RuntimeError("Logger has not been initialized.")

        self.console_level = self._validate_log_level(console_level)
        self.file_level = self._validate_log_level(file_level)

        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(self.console_level.to_logging_level())
            elif isinstance(handler, RotatingFileHandler):
                handler.setLevel(self.file_level.to_logging_level())

    def get_logger(self) -> logging.Logger:
        """Retrieve the logger instance."""
        if self.logger is None:
            self.setup_logger()

        if self.logger is None:
            raise RuntimeError("Logger setup failed, `logger` is None.")
        return self.logger

    def log_message(
            self,
            message: str,
            level: Optional[Union[LogLevel, str, int]] = None,
            exc_info: bool = False
        ) -> None:
        """Log a message with the specified log level.

        Parameters
        ----------
        message : str
            The message to be logged.
        level : Optional[Union[LogLevel, str, int]], optional
            The log level for the message, which can be a `LogLevel`,
            string, or integer. Default is None, i.e. `LogLevel.INFO`.
        exc_info : bool, optional
            If True, exception information is added to the log message.

        Raises
        ------
        RuntimeError
            If the logger is not initialized.
        """
        if self.logger is None:
            raise RuntimeError("Logger has not been initialized.")

        if level is None:
            level = LogLevel.INFO

        level = self._validate_log_level(level)

        if self.logger.isEnabledFor(level.to_logging_level()):
            log_method: Callable[[str], None] = getattr(
                self.logger, level.value, self.logger.info)
            log_method(message, stacklevel=2, exc_info=exc_info) # type: ignore