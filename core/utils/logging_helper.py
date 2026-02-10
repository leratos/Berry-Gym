"""
Logging Helper für HomeGym.

Vereinfacht das Logging im gesamten Projekt.
Nutzt strukturiertes Logging mit Context-Daten.
"""

import logging
import time
from functools import wraps
from typing import Any, Optional


def get_logger(name: str) -> logging.Logger:
    """
    Holt einen konfigurierten Logger für ein Modul.

    Args:
        name: Module name (normalerweise __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Training created", extra={'user_id': 123})
    """
    return logging.getLogger(name)


def log_performance(func):
    """
    Decorator für Performance-Logging.
    Loggt Ausführungszeit von Funktionen.

    Example:
        >>> @log_performance
        >>> def slow_function():
        >>>     time.sleep(2)
    """
    logger = logging.getLogger(func.__module__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            logger.info(
                f"{func.__name__} completed",
                extra={
                    "function": func.__name__,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "success",
                },
            )

            return result

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                f"{func.__name__} failed: {str(e)}",
                extra={
                    "function": func.__name__,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "error",
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )

            raise

    return wrapper


def log_user_action(
    logger: logging.Logger, action: str, user_id: Optional[int] = None, **context: Any
):
    """
    Loggt User-Aktionen mit strukturiertem Context.

    Args:
        logger: Logger instance
        action: Beschreibung der Aktion
        user_id: User ID (optional)
        **context: Zusätzliche Context-Daten

    Example:
        >>> logger = get_logger(__name__)
        >>> log_user_action(
        >>>     logger,
        >>>     "Training created",
        >>>     user_id=123,
        >>>     training_id=456,
        >>>     duration_minutes=60
        >>> )
    """
    extra_data = {"user_id": user_id, **context}
    logger.info(action, extra=extra_data)


def log_error_with_context(
    logger: logging.Logger, message: str, exception: Optional[Exception] = None, **context: Any
):
    """
    Loggt Fehler mit detailliertem Context.

    Args:
        logger: Logger instance
        message: Error message
        exception: Exception object (optional)
        **context: Zusätzliche Context-Daten

    Example:
        >>> try:
        >>>     risky_operation()
        >>> except Exception as e:
        >>>     log_error_with_context(
        >>>         logger,
        >>>         "Operation failed",
        >>>         exception=e,
        >>>         user_id=123,
        >>>         operation='training_creation'
        >>>     )
    """
    extra_data = {**context}

    if exception:
        extra_data["error_type"] = type(exception).__name__
        extra_data["error_message"] = str(exception)

    logger.error(message, extra=extra_data, exc_info=exception is not None)


def log_security_event(event_type: str, severity: str = "WARNING", **context: Any):
    """
    Loggt Security-Events (Login-Versuche, Permission-Violations, etc.).

    Args:
        event_type: Art des Security-Events
        severity: Log-Level (WARNING, ERROR, CRITICAL)
        **context: Context-Daten (user_id, ip_address, etc.)

    Example:
        >>> log_security_event(
        >>>     'failed_login_attempt',
        >>>     severity='WARNING',
        >>>     username='attacker',
        >>>     ip_address='192.168.1.1',
        >>>     attempts=5
        >>> )
    """
    logger = logging.getLogger("django.security")

    log_func = getattr(logger, severity.lower(), logger.warning)
    log_func(f"Security Event: {event_type}", extra={"event_type": event_type, **context})
