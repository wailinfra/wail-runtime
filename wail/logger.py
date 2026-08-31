import os
import sys

_LEVELS = {
    "silent": 0,
    "error": 1,
    "warn": 2,
    "info": 3,
    "debug": 4,
}

_current_level = _LEVELS.get(
    os.getenv("WAIL_LOG_LEVEL", "error").lower(),
    1,
)


def _log(level_name, message):
    if _LEVELS[level_name] <= _current_level:
        sys.stderr.write(f"[WAIL:{level_name.upper()}] {message}\n")


def error(msg):
    _log("error", msg)


def warn(msg):
    _log("warn", msg)


def info(msg):
    _log("info", msg)


def debug(msg):
    _log("debug", msg)
