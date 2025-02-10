import atexit
import inspect
import json
import logging
import weakref
from dotenv import load_dotenv
import logging.config
import os
from pathlib import Path
import queue
import sys
import threading
import time
from collections import defaultdict
from collections.abc import MutableMapping

from enum import Enum
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Any, Callable, Dict, Optional, Tuple, Union


from .formatter import NDJsonFormatter

load_dotenv()

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
    """Class to manage logger configuration and operations.
    
    Attributes
    ----------

    Methods
    -------
    """

    default_console_format = '%(asctime)s | %(levelname)s :: %(message)s'
    logger: Optional[logging.Logger] = None
    listener: Optional[QueueListener] = None
    fallback_logger = logging.getLogger(__name__)

    def __init__(
            self,
            module_name: str,
            project_name: Optional[str] = None,
            folder_path: Union[str, Path] = "./logs",
            max_file_size: int = 500 * 1024 * 1024,
            backup_count: int = 3,
            console_level: Union[LogLevel, str, int] = LogLevel.INFO,
            file_level: Union[LogLevel, str, int] = LogLevel.DEBUG,
            console_message_format: Optional[str] = None,
            console_date_format: str = "%Y-%m-%d %H:%M:%S"
        ) -> None:
        self.name = module_name
        self.project_name = project_name or module_name
        self.log_dir = Path(folder_path)
        if max_file_size <= 0:
            raise ValueError("max_file_size must be a positive integer.")
        self.max_size = max_file_size
        self.backup_count = backup_count
        self.console_level = self._validate_log_level(console_level)
        self.file_level = self._validate_log_level(file_level)
        self.format_message = console_message_format or self.default_console_format
        self.date_format = console_date_format

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
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up handlers
        self._setup_handlers()

        # Queue listener for asynchronous logging
        self._start_listener()

        return self.logger

    def _validate_log_level(self, level: Union[LogLevel, str, int]) -> LogLevel:
        """Validate and convert a log level input to a LogLevel instance."""
        if isinstance(level, LogLevel):
            return level
        if isinstance(level, str):
            return LogLevel.from_string(level)
        if isinstance(level, int):
            return LogLevel.from_int(level)
        self.fallback_logger.error(
            "No logger was initialized because log level type is incorrect.")
        raise ValueError(
            f"Log level must be a string, integer, or LogLevel instance. Got: {type(level)}"
        )

    def _setup_handlers(self):
        """Set up console and file handlers for the logger."""
        timestamp = time.strftime('%Y%m%d')
        log_file = self.log_dir / f"{self.project_name}_{timestamp}.log"

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level.to_logging_level())
        console_handler.setFormatter(
            logging.Formatter(self.format_message, datefmt=self.date_format)
        )

        # File handler with JSON formatter
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.file_level.to_logging_level())
        file_handler.setFormatter(NDJsonFormatter())

        # Queue handler
        log_queue = queue.Queue(-1)
        queue_handler = QueueHandler(log_queue)
        if self.logger is None:
            self.fallback_logger.error("No logger was initialized correctly.")
            raise RuntimeError("Logger setup failed, `logger` is None.")
        self.logger.addHandler(queue_handler)

        self.listener = QueueListener(
            log_queue, console_handler, file_handler, respect_handler_level=True
        )

    def _start_listener(self):
        """Start the queue listener."""
        if not self.listener:
            self.fallback_logger.error(
                "No logger was initialized because the listener could not be started.")
            raise RuntimeError("Listener has not been initialized.")
        self.listener.start()
        import atexit

        atexit.register(self.listener.stop)

    def update_levels(
            self,
            console_level: Union[LogLevel, str, int],
            file_level: Union[LogLevel, str, int],
        ) -> None:
        """Update log levels for console and file handlers."""
        if self.logger is None:
            self.fallback_logger.error(
                "No logger was initialized, content addressed to fallback.")
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
            self.fallback_logger.error("No logger was initialized correctly.")
            raise RuntimeError("Logger setup failed, `logger` is None.")
        return self.logger

    def log_message(
            self,
            message: str,
            level: Optional[Union[LogLevel, str, int]] = None,
            exc_info: bool = False,
            extra: Optional[Dict[str, Any]] = None
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
        extra : Optional[Dict[str, Any]], optional
            Additional context to be included in the log message.

        Raises
        ------
        RuntimeError
            If the logger is not initialized.
        """
        if self.logger is None:
            self.fallback_logger.error(
                "No logger was initialized, content addressed to fallback.")
            raise RuntimeError("Logger has not been initialized.")

        if level is None:
            level = LogLevel.INFO

        level = self._validate_log_level(level)

        if self.logger.isEnabledFor(level.to_logging_level()):
            log_method: Callable[[str], None] = getattr(
                self.logger, level.value, self.logger.info)
            log_method(
                message,
                stacklevel=2, # type: ignore
                exc_info=exc_info, # type: ignore
                extra=extra # type: ignore
            )

class Singleton(type):
    """A metaclass for creating Singleton classes.

    This metaclass ensures that a class has only one instance, even if
    constructed with different arguments. It uses a lock to ensure
    thread safety during instance creation. The instance is stored in a
    dictionary with a key derived from the class and its initialization
    arguments.
    """
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        """Returns the singleton instance of the class, creating it if
        it doesn't exist. The instance is keyed by the class and its
        initialization arguments.
        """
        with cls._lock:
            if cls.__init__ is object.__init__:
                # No custom `__init__`, use class itself as key
                key = cls
            else:
                sig = inspect.signature(cls.__init__)
                bound_args = sig.bind(None, *args, **kwargs)
                bound_args.apply_defaults()

                # Convert arguments to a hashable form
                def make_hashable(value):
                    if isinstance(value, (int, float, str, bool, type(None))):
                        # Already hashable
                        return value
                    try:
                        # Convert non-hashables
                        return json.dumps(value, sort_keys=True)
                    except (TypeError, ValueError):
                        # Fallback to string representation
                        return repr(value)

                key = (
                    cls,
                    frozenset((k, make_hashable(v))
                              for k, v in bound_args.arguments.items())
                )

            if key not in cls._instances:
                cls._instances[key] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[key]

class LoggerHandler(metaclass=Singleton):
    """A class to manage logging configuration for an application.

    This class provides methods to set up logging with console and file
    handlers, using a rotating file handler for log file management. It
    supports different log levels for console and file outputs and uses
    a queue for asynchronous logging.
    
    Attributes
    ----------
    backup_count : int
        The number of backup files to keep.
    console_date_fmt : str
        The date format for console log messages.
    console_level : int
        The logging level for console output.
    console_msg_fmt : str
        The format for console log messages.
    default_console_format : str
        The default format for console log messages.
    default_date_format : str
        The default date format for log messages.
    fallback_logger : logging.Logger
        A logger used for fallback error logging.
    file_date_fmt : str
        The date format for file log messages.
    file_level : int
        The logging level for file output.
    logging_enabled : bool
        Indicates if logging is enabled based on environment variables.
    log_dir : str
        The directory path where log files are stored.
    max_size : int
        The maximum size of a log file before it is rotated.

    Methods
    -------
    `setup(component: str)` -> None
        Sets up console and file handlers for logging.
    `get_logger(name: str, level: Optional[Union[LogLevel, str, int]])` -> logging.Logger
        Retrieves a logger instance with the specified name and level.
    """

    logging_enabled: bool
    fallback_logger: logging.Logger
    default_console_format: str
    default_date_format: str
    _handlers_added: bool

    def __init__(
            self,
            folder_path: Union[str, Path] = "./logs",
            max_file_size: Optional[int] = 150 * 1024 * 1024,  # 150MB,
            backup_count: Optional[int] = 3,
            console_level: Optional[Union[LogLevel, str, int]] = LogLevel.INFO,
            file_level: Optional[Union[LogLevel, str, int]] = LogLevel.DEBUG,
            console_message_format: Optional[str] = None,
            console_date_format: Optional[str] = None,
            file_date_format: Optional[str] = None,
        ) -> None:
        """
        Parameters
        ----------
        folder_path : Union[str, Path], optional
            The directory path where log files will be stored. Defaults
            to "./logs".
        max_file_size : Optional[int], optional
            The maximum size of a log file in bytes before it is
            rotated. By default 157286400. If None, using the default.
        backup_count : Optional[int], optional
            The number of backup files to keep. Defaults to 3. If None,
            using the default.
        console_level : Optional[Union[LogLevel, str, int]], optional
            The logging level for console output. If None, the default
            setting, which is `LogLevel.INFO`, is used.
        file_level : Optional[Union[LogLevel, str, int]], optional
            The logging level for file output. If None, the default
            setting, which is `LogLevel.DEBUG`, is used.
        console_message_format : Optional[str], optional
            The format for console log messages. Defaults to None, using
            the default format.
        console_date_format : Optional[str], optional
            The date format for console log messages. Defaults to None,
            using the default format.
        file_date_format : Optional[str], optional
            The date format for file log messages. Defaults to None,
            using the default format.

        Raises
        ------
        ValueError
            If max_file_size is not a positive integer.
        """
        # Check if logging is disabled via an environment variable
        self.logging_enabled = os.environ.get(
            'LOGGING_ENABLED', "true").lower() in ("1", "true", "yes")

        self.fallback_logger = logging.getLogger("fallback")
        self.fallback_logger.addHandler(logging.StreamHandler(sys.stderr))

        self.default_console_format = '%(asctime)s | %(levelname)s - %(lineno)d : %(message)s'
        self.default_date_format = "%Y-%m-%d %H:%M:%S"

        self._handlers_added = False

        self.log_dir = self._validate_logging_folder(folder_path)

        if (max_file_size is not None and
            (not isinstance(max_file_size, int) or max_file_size <= 0)):
            raise ValueError("`max_file_size` must be a positive integer.")
        self.max_size = max_file_size if max_file_size is not None else 500 * 1024 * 1024

        if (backup_count is not None and
            (not isinstance(backup_count, int) or backup_count <= 0)):
            raise ValueError("`backup_count` must be a positive integer.")
        self.backup_count = backup_count if backup_count is not None else 3

        self.console_level = self._validate_log_level(
            console_level or LogLevel.INFO)
        self.file_level = self._validate_log_level(
            file_level or LogLevel.DEBUG)

        self.console_msg_fmt = console_message_format or self.default_console_format
        self.console_date_fmt = console_date_format or self.default_date_format
        self.file_date_fmt = file_date_format or self.default_date_format

    def setup(self, component: Optional[str] = None) -> None:
        """Set up console and file handlers for the logger."""
        if not self.logging_enabled:
            print("[LoggerHandler] Logging is disabled via environment variable.")
            return

        if self._handlers_added:
            return  # Prevent adding handlers multiple times

        # Root logger captures all levels
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(
            logging.Formatter(self.console_msg_fmt, datefmt=self.console_date_fmt)
        )

        # self._manage_urllib_logging()

        # File handler with NDJSON formatter
        timestamp = time.strftime('%Y%m%d')
        log_file = self.log_dir / "{}{}.log".format(
            f"{component}_" if component else "",
            timestamp
        )
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(
            NDJsonFormatter(datefmt=self.file_date_fmt)
        )

        # Attach handlers only once (avoid duplicates)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        # Queue-based async logging
        log_queue = queue.Queue(-1)
        queue_handler = QueueHandler(log_queue)
        queue_handler.setLevel(self.console_level)
        queue_handler.setFormatter(
            logging.Formatter(self.console_msg_fmt, datefmt=self.console_date_fmt)
        )

        # QueueListener with handlers for asynchronous logging
        listener = QueueListener(
            log_queue, console_handler, file_handler, respect_handler_level=True
        )
        try:
            self._start_listener(listener)
        except Exception as e:
            self.fallback_logger.error(f"Failed to start QueueListener: {e}")

        self._handlers_added = True  # Mark handlers as added
        print("[LoggerHandler] Logging is enabled and configured.")

    def get_logger(
            self,
            name: str,
            level: Optional[Union[LogLevel, str, int]] = None
        ) -> logging.Logger:
        """Retrieve the logger instance."""
        logger = logging.getLogger(name)

        if level:
            logger.setLevel(self._validate_log_level(level))

        return logger

    def _validate_logging_folder(self, folder_path: Union[str, Path]) -> Path:
        """Validate and create the logging directory if it does not exist."""
        folder_path = Path(folder_path)
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            return folder_path
        except Exception as e:
            self.fallback_logger.error(f"Failed to create log directory: {e}")
            raise

    def _validate_log_level(self, level: Union[LogLevel, str, int]) -> int:
        """Validate and convert a log level input to a logging module equivalent."""
        if isinstance(level, LogLevel):
            return level.to_logging_level()
        if isinstance(level, str):
            return LogLevel.from_string(level).to_logging_level()
        if isinstance(level, int):
            return LogLevel.from_int(level).to_logging_level()

        self.fallback_logger.error("Invalid log level provided.")
        raise ValueError(f"Invalid log level: {level}")

    def _manage_urllib_logging(self) -> None:
        # Fix logging format to prevent incorrect argument conversion
        urllib3_logger = logging.getLogger("urllib3")
        urllib3_logger.setLevel(logging.DEBUG)

        # Ensure logging handlers use correct format
        for handler in urllib3_logger.handlers:
            handler.setFormatter(logging.Formatter(self.console_msg_fmt))

    def _start_listener(self, listener: QueueListener) -> None:
        """Start the queue listener."""
        listener.start()
        atexit.register(listener.stop)