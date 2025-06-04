# core/logger_config.py

import os
import logging
from datetime import datetime
from core.config import Config  # Import Config to get settings


def setup_logger(config: Config, name: str = None) -> logging.Logger:
    """
    Create (and return) a timestamped logger under config.LOG_DIRECTORY.
    - Ensures LOG_DIRECTORY is within the project root (as validated in config.py).
    - Creates the directory with os.makedirs (catching permission errors).
    - Creates a log file named "<LOGGER_NAME>_YYYYMMDD_HHMMSS.log".
    - Sets permissions on the log file to 0o600 (owner read/write only).
    """

    # Canonicalize and re-validate the log directory
    project_root = os.path.realpath(os.getcwd())
    log_dir = os.path.realpath(config.LOG_DIRECTORY)
    if not log_dir.startswith(project_root):
        raise RuntimeError(f"LOG_DIRECTORY must be inside the project directory: {log_dir}")

    # Attempt to create the log directory if it doesn't exist
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Could not create log directory '{log_dir}': {e}")

    # Build a timestamped filename
    logger_name = name if name else config.LOGGER_NAME
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"{logger_name}_{timestamp}.log")

    # Create (or retrieve) the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(config.LOG_LEVEL)  # Use log level from config

    # If no handlers yet, attach a FileHandler
    if not logger.handlers:
        try:
            file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to open log file '{log_filename}': {e}")

        file_handler.setLevel(config.LOG_LEVEL)
        formatter = logging.Formatter(
            config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # After the handler is attached (and the file is created on first write),
        # explicitly set file permissions to 0o600 (owner read/write only).
        try:
            # Note: The file might not exist until the first log record is emitted.
            # To ensure it exists, we can emit a dummy record at DEBUG level.
            logger.debug("Initializing log file and setting secure permissions.")
            if os.path.exists(log_filename):
                os.chmod(log_filename, 0o600)
        except OSError as e:
            raise RuntimeError(f"Could not set permissions on log file '{log_filename}': {e}")

    return logger
