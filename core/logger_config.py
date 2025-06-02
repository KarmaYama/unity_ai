#core/logger_config.py

import os
import logging
from datetime import datetime
from core.config import Config # Import Config to get settings

# Create (and return) a timestamped logger under "log/".
# Now accepts a Config object
def setup_logger(config: Config, name: str = None):
    # Use config for log directory, logger name, log level, and format
    log_dir = config.LOG_DIRECTORY
    logger_name = name if name else config.LOGGER_NAME

    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(
        log_dir, f"{logger_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    logger = logging.getLogger(logger_name)
    logger.setLevel(config.LOG_LEVEL) # Use log level from config

    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(config.LOG_LEVEL) # Use log level from config
    formatter = logging.Formatter(
        config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT # Use format and date format from config
    )
    file_handler.setFormatter(formatter)

    # Avoid adding multiple handlers if already set
    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger
