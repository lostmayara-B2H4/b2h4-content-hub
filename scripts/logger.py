#!/usr/bin/env python3
"""B2H4 Shared Logger — logging estruturado para todos os serviços."""
import logging
import sys
import os
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Formato estruturado com timestamp, level, service e mensagem."""

    def __init__(self, service_name="b2h4"):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")
        level = record.levelname.ljust(7)
        msg = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg += f"\n{record.exc_text}"
        return f"[{ts}] {level} [{self.service_name}] {msg}"


def get_logger(name="b2h4", level=None):
    """Retorna um logger configurado com formato estruturado."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        service = os.environ.get("SERVICE_NAME", name)
        handler.setFormatter(StructuredFormatter(service))
        logger.addHandler(handler)
    if level:
        logger.setLevel(level)
    elif os.environ.get("LOG_LEVEL"):
        logger.setLevel(getattr(logging, os.environ["LOG_LEVEL"].upper(), logging.INFO))
    else:
        logger.setLevel(logging.INFO)
    return logger
