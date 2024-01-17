import json
import logging
import sys
from enum import Enum

from loguru import logger


class LoggingFormat(str, Enum):
    CONSOLE = "CONSOLE"
    JSON = "JSON"


def json_format(record: dict) -> str:
    return record["message"]


def setup_logger(logger_path: str = "./example.log",
                 level: str = "INFO",
                 fmt: LoggingFormat = LoggingFormat.CONSOLE):
    level: int = logging.getLevelName(level.upper())
    if type(level) is not int:
        level = logging.INFO

    fileHandler = logging.FileHandler(logger_path, mode='w')

    if fmt == LoggingFormat.JSON:
        logger.remove(None)
        logger.add(
            sys.stdout,
            level=level,
            format="{message}",
            colorize=False,
            serialize=True,
        )
    elif fmt == LoggingFormat.CONSOLE:
        logger.remove(None)
        logger.add(sys.stdout, level=level, colorize=True)
        logger.add(fileHandler, level=logging.DEBUG)

    return logger


def get_logger(*args, **kwargs):
    return logger
