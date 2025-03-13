"""Logging configuration module for the JSON processor application."""
import os
import logging
from logging.handlers import RotatingFileHandler
import config

def setup_logging():
    """Set up logging with appropriate handlers and formatters."""
    # Ensure logs directory exists
    os.makedirs(config.LOGS_FOLDER, exist_ok=True)

    # Log file paths
    app_log_path = os.path.join(config.LOGS_FOLDER, 'app.log')
    error_log_path = os.path.join(config.LOGS_FOLDER, 'error.log')
    debug_log_path = os.path.join(config.LOGS_FOLDER, 'debug.log')

    # Log formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s'
    )
    simple_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    
    # Console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # 1. App Logger (INFO level)
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    app_handler = RotatingFileHandler(
        app_log_path, maxBytes=5*1024*1024, backupCount=5
    )
    app_handler.setFormatter(simple_formatter)
    app_handler.setLevel(logging.INFO)
    app_logger.addHandler(app_handler)

    # 2. Error Logger (ERROR level)
    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)
    error_handler = RotatingFileHandler(
        error_log_path, maxBytes=2*1024*1024, backupCount=10
    )
    error_handler.setFormatter(detailed_formatter)
    error_handler.setLevel(logging.ERROR)
    error_logger.addHandler(error_handler)

    # 3. Debug Logger (DEBUG level)
    debug_logger = logging.getLogger('debug')
    debug_logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    debug_handler = RotatingFileHandler(
        debug_log_path, maxBytes=10*1024*1024, backupCount=3
    )
    debug_handler.setFormatter(detailed_formatter)
    debug_handler.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    debug_logger.addHandler(debug_handler)

    return {
        'app': app_logger,
        'error': error_logger,
        'debug': debug_logger
    }

# Create a function to get loggers
def get_loggers():
    """Get configured logger instances."""
    return {
        'app': logging.getLogger('app'),
        'error': logging.getLogger('error'),
        'debug': logging.getLogger('debug')
    }