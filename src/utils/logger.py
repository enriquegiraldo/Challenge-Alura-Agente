"""
Logger estructurado con rich para consola colorida.
"""
from __future__ import annotations

import logging
from rich.logging import RichHandler


def setup_logger(name: str = "aurora", level: int = logging.INFO) -> logging.Logger:
    """Configura y devuelve un logger con rich."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,
        markup=True,
        log_time_format="[%X]",
    )
    handler.setLevel(level)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# Logger por defecto
log = setup_logger()
