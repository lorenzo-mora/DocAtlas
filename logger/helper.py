from contextlib import contextmanager
import logging
import threading
import time
from typing import Any, Generator, Optional, Union

from .setup import InstanceAdapter
from utils import contains_placeholders


def log_status(
    interval: float,
    stop_event: threading.Event,
    message: str,
    logger_instance: Optional[Union[logging.Logger, InstanceAdapter]] = None
) -> None:
    """Periodically logs a status message at a specified interval until
    a stop event is set.

    This function logs a formatted message at regular intervals using
    the provided logger. If no logger is provided, it prints the message
    to the console. The message can include placeholders for elapsed
    time, which will be replaced with the actual elapsed time since the
    start of logging.

    Parameters
    ----------
    interval : float
        The time interval in seconds between log messages. Must be a
        positive number.
    stop_event : threading.Event
        An event object to signal when to stop logging.
    message : str
        The message to log. Can contain placeholders for elapsed time.
    logger_instance : logging.Logger or InstanceAdapter or None, optional
        The logger to use for logging messages. If None, messages are
        printed to the console; by default None

    Raises
    ------
    ValueError
        If the interval is not a positive number.
    """
    if interval <= 0:
        raise ValueError("Interval must be a positive number.")

    try:
        start_time = time.perf_counter() if contains_placeholders(message) else None

        while not stop_event.is_set():
            if start_time is not None:
                elapse_time = time.perf_counter() - start_time
                fmt_msg = message.format(elapse_time)
            else:
                fmt_msg = message

            if logger_instance:
                logger_instance.debug(fmt_msg)
            else:
                print(fmt_msg)

            time.sleep(interval)

    except Exception as e:
        error_message = f"Logging thread encountered an error: {e}"
        if logger_instance:
            logger_instance.error(error_message)
        else:
            print(error_message)

@contextmanager
def status_logging_thread(
    logger_instance: Optional[Union[logging.Logger, InstanceAdapter]],
    message: Optional[str] = None,
    frequency: float = 5,
    **kwargs
) -> Generator[None, Any, None]:
    """Context manager for managing (creating and deleting) a status
    logging thread."""
    if kwargs and isinstance(logger_instance, InstanceAdapter):
        for k, v in kwargs.items():
            logger_instance.add_context(k, v)

    stop_event = threading.Event()
    log_thread = threading.Thread(
        target=log_status,
        args=(frequency, stop_event, message, logger_instance),
        daemon=True
    )

    try:
        log_thread.start()  # Start the logging thread
        yield  # Allow the context block to execute
    finally:
        stop_event.set()  # Signal the thread to stop
        log_thread.join(timeout=10)  # Ensure the thread stops gracefully

@contextmanager
def timed_block(
    message: Optional[str] = None,
    logger_instance: Optional[Union[logging.Logger, InstanceAdapter]] = None
) -> Generator[None, Any, None]:
    """A context manager to measure and log the execution time of a code
    block.

    Parameters
    ----------
    message : str or None, optional
        A custom message to prefix the elapsed time log, by default
        None.
    logger_instance : Logger or InstanceAdapter or None, optional
        If not provided, messages will be printed to the console.
        Default is None.

    Yields
    ------
    Generator[None, Any, None]
        This context manager does not yield any value.

    Raises
    ------
    Exception
        Any exception that occurs within the context block.
    """
    start_time: float = time.perf_counter()
    try:
        yield
    except Exception as e:
        if logger_instance:
            logger_instance.error(f"Exception occurred: {e}", exc_info=True)
        else:
            print(f"Exception occurred: {e}")
        raise
    finally:
        elapsed_time: float = time.perf_counter() - start_time

        info_msg = "Elapsed time"
        if message:
            info_msg = message

        elapsed_msg = f'{info_msg}: {elapsed_time:.2f} sec.'
        if logger_instance:
            logger_instance.debug(elapsed_msg, stacklevel=3)
        else:
            print(elapsed_msg)