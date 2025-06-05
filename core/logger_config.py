# core/logger_config.py

import os
import logging
from datetime import datetime
from pathlib import Path
from core.config import Config

def setup_logger(config: Config, name: str = None) -> logging.Logger:
    """
    Create (and return) a timestamped logger under config.LOG_DIRECTORY.
    - Ensures LOG_DIRECTORY is within the project root (as validated in config.py).
    - Creates the directory with os.makedirs (catching permission errors).
    - Creates a log file named "<LOGGER_NAME>_YYYYMMDD_HHMMSS.log".
    - Sets permissions on the log file to 0o600 (owner read/write only).
    """

    project_root = Path(os.getcwd()).resolve()
    log_dir = Path(config.LOG_DIRECTORY).resolve()
    if not log_dir.is_relative_to(project_root):
        raise RuntimeError(f"LOG_DIRECTORY must be inside the project directory: {log_dir}")

    try:
        # Create directory with restrictive permissions if it does not exist
        log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(log_dir, 0o700)
    except Exception as e:
        raise RuntimeError(f"Could not create or lock down log directory '{log_dir}': {e}")

    logger_name = name if name else config.LOGGER_NAME
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"{logger_name}_{timestamp}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(config.LOG_LEVEL)

    if not logger.handlers:
        try:
            file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to open log file '{log_filename}': {e}")

        file_handler.setLevel(config.LOG_LEVEL)
        formatter = logging.Formatter(config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Emit a dummy DEBUG message so the file is created immediately
        logger.debug("Initializing log file and setting secure permissions.")

        # After first write, set file permissions to 0o600
        try:
            if log_filename.exists():
                os.chmod(log_filename, 0o600)
        except Exception as e:
            raise RuntimeError(f"Could not set permissions on log file '{log_filename}': {e}")

    return logger
