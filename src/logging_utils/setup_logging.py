import logging
import logging.config
import colorlog
import atexit
from core.files import GENERAL_SETTINGS
import json
import os


try:
    with open(GENERAL_SETTINGS, "r") as f:
        general_settings = json.load(f)
except:
    print("Warning: no general settings file. Using default fallbacks")
    general_settings = {}

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

    match str(general_settings.get("loggingLevel", "DEBUG")).upper():
        case "DEBUG":
            level = "DEBUG"
        case "INFO":
            level = "INFO"
        case "WARNING":
            level = "WARNING"
        case "ERROR":
            level = "ERROR"
        case "CRITICAL":
            level = "CRITICAL"
        case _:
            level = "DEBUG"

    LOGGING_CONFIG["loggers"]["root"]["level"] = level
    LOGGING_CONFIG["handlers"]["file"]["maxBytes"] = (
        general_settings.get("logFileMaxSizeMB", 2) * 1024 * 1024
    )
    LOGGING_CONFIG["handlers"]["file"]["backupCount"] = general_settings.get(
        "logFileBackupCount", 3
    )

    try:
        logging.config.dictConfig(LOGGING_CONFIG)
        queue_handler = logging.getHandlerByName("queue_handler")
        if queue_handler is not None:
            queue_handler.listener.start()
            atexit.register(queue_handler.listener.stop)
    except Exception as e:
        print(f"Error: {e}")
        print(
            "ERROR: THERE IS A PROBLEM WITH YOUR CONFIGURATION FILES. PLEASE FIX AND RE-RUN"
        )
        os._exit(1)
