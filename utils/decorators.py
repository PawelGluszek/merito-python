"""Custom decorators for the duplicate file finder."""

import functools
import logging
import time

logger = logging.getLogger(__name__)


def measure_time(func):
    """Log execution time of the decorated function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("[%s] executed in %.4f s", func.__name__, elapsed)
        return result
    return wrapper


def retry(attempts: int = 3, delay: float = 0.5, exceptions: tuple[type[Exception], ...] = (Exception,)):
    """Retry the decorated function on failure.

    Args:
        attempts: Maximum number of attempts.
        delay: Seconds to wait between retries.
        exceptions: Tuple of exception types that trigger a retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    logger.warning(
                        "[%s] attempt %d/%d failed: %s",
                        func.__name__, attempt, attempts, exc,
                    )
                    if attempt < attempts:
                        time.sleep(delay)
            raise RuntimeError(
                f"{func.__name__}: exhausted {attempts} attempts"
            ) from last_exception
        return wrapper
    return decorator


def log_call(func):
    """Log each call with its arguments."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args_repr = ", ".join(
            [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
        )
        logger.debug("[%s] called with (%s)", func.__name__, args_repr)
        result = func(*args, **kwargs)
        logger.debug("[%s] returned %r", func.__name__, result)
        return result
    return wrapper
