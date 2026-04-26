# config/logger.py
# ============================================
# Centralized Logging System
# ============================================

import logging
import os
from datetime import datetime

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger.
    Usage: logger = get_logger(__name__)
    """
    # Create logs directory if not exists
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)

    if not logger.handlers:  # Avoid duplicate handlers
        logger.setLevel(logging.INFO)

        # Console handler - shows INFO and above
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        ))

        # File handler - stores everything
        file_handler = logging.FileHandler(
            f"logs/trading_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))

        logger.addHandler(console)
        logger.addHandler(file_handler)

    return logger
