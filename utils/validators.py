"""System validation utilities for the JSON processor application."""
import os
import sys
import logging
import config

logger = logging.getLogger('error')

def check_system_requirements():
    """Check if system meets requirements to run the application.
    
    Returns:
        bool: True if system meets requirements, False otherwise
    """
    try:
        # Check Python version
        if sys.version_info < (3, 7):
            logger.critical("Python 3.7 or higher is required")
            return False
        
        # Check disk space
        if os.name == 'posix':  # Linux/Unix/MacOS
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_mb = free / (1024 * 1024)
            if free_mb < config.MIN_DISK_SPACE_MB:
                logger.critical(f"Low disk space: {free_mb:.2f} MB free, minimum required: {config.MIN_DISK_SPACE_MB} MB")
                return False
        
        # Check folder permissions
        required_folders = [
            config.DATA_FOLDER,
            config.VALIDATED_FOLDER, 
            config.RETURNS_FOLDER,
            config.LOGS_FOLDER, 
            config.PROCESSING_FOLDER
        ]
        
        for folder in required_folders:
            if os.path.exists(folder) and not os.access(folder, os.R_OK | os.W_OK):
                logger.critical(f"Insufficient permissions for folder '{folder}'. Need read/write access.")
                return False
        
        # Check that required environment variables are set
        missing_vars = [var for var in config.REQUIRED_ENV_VARS if not os.environ.get(var)]
        if missing_vars:
            logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}")
            logger.info("Please create a .env file with the required variables or set them in your environment")
            return False
        
        return True
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        logger.critical(f"Error checking system requirements: {str(e)}\n{stack_trace}")
        return False