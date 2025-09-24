import logging
import logging.config
import colorlog
import atexit

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_formatters": False,
    "filters": {
        "redacted_filter": {
            "()": "logging_utils.RedactedFilter",
        },
    },
    "formatters": {
        "simple": {"format": "%(levelname)s: %(message)s"},
        "json": {
            "()": "logging_utils.JSONFormatter",
            "fmt_keys": {
                "level": "levelname",
                "message": "message",
                "timestamp": "timestamp",
                "logger": "name",
                "module": "module",
                "function": "funcName",
                "line": "lineno",
                "thread_name": "threadName",
            },
        },
        "color": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s[%(levelname)-8s | %(module)-15s | L%(lineno)-4d] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            "log_colors": {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "color",
            "filters": [
                "redacted_filter",
            ],
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "logs/log.jsonl",
            "maxBytes": 10_000,
            "backupCount": 3,
        },
        "queue_handler": {
            "class": "logging.handlers.QueueHandler",
            "handlers": ["stdout", "file"],
            "respect_handler_level": True,
        },
    },
    "loggers": {
        "root": {
            "level": "DEBUG",
            "handlers": [
                "queue_handler",
            ],
        }
    },
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)
