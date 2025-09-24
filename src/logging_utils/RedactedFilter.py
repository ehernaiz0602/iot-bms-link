import logging


class RedactedFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        return "REDACTED" not in message and "User-Agent" not in message
