"""Application logging: a rotating file in the user data directory, plus console.

Until now a failure only left a traceback in whatever terminal launched the
app — useless for a desktop program. Everything goes to
``<data dir>/logs/oms.log`` (rotated), the level is controlled with
``OMS_LOG_LEVEL``, and uncaught exceptions are written with their traceback
before Python's default hook runs.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from oms_core import paths as paths_mod

#: Env var that overrides the level (DEBUG, INFO, WARNING, ERROR).
ENV_LOG_LEVEL = "OMS_LOG_LEVEL"

#: Folder and file, inside the per-user data directory.
LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "oms.log"

#: Rotation: keep five 2 MB files, enough for weeks of use.
MAX_BYTES = 2_000_000
BACKUP_COUNT = 5

DEFAULT_LEVEL = "INFO"

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

#: Marker so a second call reconfigures instead of stacking handlers.
_HANDLER_ATTR = "_oms_handler"


def log_dir(
    env: dict[str, str] | None = None, *, platform: str | None = None
) -> Path:
    """``<data dir>/logs`` — beside the database, never in Documents."""
    return paths_mod.data_dir(env, platform=platform) / LOG_DIR_NAME


def log_file(
    env: dict[str, str] | None = None, *, platform: str | None = None
) -> Path:
    return log_dir(env, platform=platform) / LOG_FILE_NAME


def _level_from(value: object) -> int:
    if isinstance(value, int):
        return value
    name = str(value or DEFAULT_LEVEL).upper()
    return getattr(logging, name, logging.INFO)


def setup_logging(
    level: object = None,
    *,
    console: bool = True,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    filename: str | Path | None = None,
) -> Path:
    """Configure the root logger and return the file it writes to."""
    env_map = os.environ if env is None else env
    target = Path(filename) if filename is not None else log_file(env_map, platform=platform)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved = _level_from(level if level is not None else env_map.get(ENV_LOG_LEVEL))

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_ATTR, False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(_FORMAT)
    file_handler = logging.handlers.RotatingFileHandler(
        target, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    setattr(file_handler, _HANDLER_ATTR, True)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(resolved)
    root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler()
        setattr(stream, _HANDLER_ATTR, True)
        stream.setFormatter(formatter)
        stream.setLevel(resolved)
        root.addHandler(stream)

    root.setLevel(resolved)
    logging.getLogger(__name__).info("logging iniciado en %s (nivel %s)",
                                     target, logging.getLevelName(resolved))
    return target


def install_excepthook() -> None:
    """Log uncaught exceptions before the default hook prints them."""
    logger = logging.getLogger("oms_core.unhandled")
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_tb)
            return
        logger.critical("excepción no controlada", exc_info=(exc_type, exc_value, exc_tb))
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


__all__ = [
    "BACKUP_COUNT",
    "DEFAULT_LEVEL",
    "ENV_LOG_LEVEL",
    "LOG_DIR_NAME",
    "LOG_FILE_NAME",
    "MAX_BYTES",
    "install_excepthook",
    "log_dir",
    "log_file",
    "setup_logging",
]
