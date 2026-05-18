import logging
import sys


def setup_logger(name: str) -> logging.Logger:
    """创建统一格式的 logger"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
