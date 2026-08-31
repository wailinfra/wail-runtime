import logging
import os

LOG_LEVEL = os.getenv("WAIL_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("WAIL_LOG_FORMAT", "plain")


def _create_logger():
    logger = logging.getLogger("wail")
    logger.setLevel(LOG_LEVEL)

    handler = logging.StreamHandler()

    if LOG_FORMAT == "json":
        formatter = logging.Formatter(
            '{"level":"%(levelname)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter("[%(levelname)s] %(message)s")

    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)

    return logger


logger = _create_logger()
