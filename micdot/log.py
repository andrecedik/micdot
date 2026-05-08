from __future__ import annotations
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup() -> logging.Logger:
    log_dir = Path.home() / "Library" / "Logs" / "MicDot"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("micdot")
    if logger.handlers:
        return logger  # already configured (e.g. settings subprocess)

    logger.setLevel(logging.DEBUG)

    fh = RotatingFileHandler(
        log_dir / "micdot.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    logger.addHandler(fh)

    if not getattr(sys, "frozen", False):
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))
        logger.addHandler(sh)

    return logger
