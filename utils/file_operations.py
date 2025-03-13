"""File operation utilities for the JSON processor application."""
import os
import time
import shutil
import uuid
import logging
import config

# Get loggers
logger = logging.getLogger('debug')
error_logger = logging.getLogger('error')

def wait_for_file_access(file_path, max_attempts=None, delay=None):
    """Wait for a file to be accessible with multiple retries.
    
    Args:
        file_path: Path to the file to check
        max_attempts: Maximum number of attempts to try accessing the file
        delay: Delay in seconds between attempts
    
    Returns:
        bool: True if file is accessible, False otherwise
    """
    max_attempts = max_attempts or config.FILE_ACCESS_MAX_ATTEMPTS
    delay = delay or config.FILE_ACCESS_DELAY
    
    for attempt in range(max_attempts):
        if not os.path.exists(file_path):
            logger.debug(f"File does not exist yet (attempt {attempt+1}): {file_path}")
            time.sleep(delay)
            continue
            
        try:
            # Try to open the file to ensure it's not locked
            with open(file_path, 'rb') as f:
                # Read a small amount to check if file is accessible
                f.read(1)
            return True
        except (PermissionError, OSError) as e:
            logger.debug(f"File not accessible yet (attempt {attempt+1}): {str(e)}")
            time.sleep(delay)
    
    return False

def move_file(source_path, dest_folder, filename, max_attempts=None):
    """Safely move a file to destination folder with retries.
    
    Args:
        source_path: Path to the source file
        dest_folder: Destination folder
        filename: Desired filename at destination
        max_attempts: Maximum number of attempts to try moving the file
    
    Returns:
        bool: True if move succeeded, False otherwise
    """
    max_attempts = max_attempts or config.FILE_MOVE_MAX_ATTEMPTS
    dest_path = os.path.join(dest_folder, filename)
    
    for attempt in range(max_attempts):
        try:
            # Check if destination exists and handle it
            if os.path.exists(dest_path):
                alternative_name = f"{str(uuid.uuid4())[:8]}_{filename}"
                dest_path = os.path.join(dest_folder, alternative_name)
                logger.debug(f"Destination exists, using alternative name: {alternative_name}")
            
            shutil.copy2(source_path, dest_path)
            logger.debug(f"Successfully moved file to {dest_path}")
            return True
        except (PermissionError, OSError) as e:
            error_logger.error(f"Failed to move file on attempt {attempt+1}: {str(e)}")
            time.sleep(1)
    
    error_logger.error(f"Failed to move file after {max_attempts} attempts: {source_path}")
    return False

def sanitize_data_for_logging(data):
    """Create a copy of data with sensitive information masked for safe logging.
    
    Args:
        data: Data structure to sanitize
        
    Returns:
        Data structure with sensitive information masked
    """
    if data is None:
        return None
    
    # For primitive types, return as is
    if not isinstance(data, (dict, list)):
        return data
    
    # For lists, sanitize each element
    if isinstance(data, list):
        return [sanitize_data_for_logging(item) for item in data]
        
    # For dictionaries, sanitize each value
    sanitized = {}
    for key, value in data.items():
        # Mask card numbers
        if key == 'CustomerCardNumber' and isinstance(value, str) and len(value) >= 8:
            sanitized[key] = '*' * (len(value) - 4) + value[-4:]
        # Process nested dictionaries
        elif isinstance(value, dict):
            sanitized[key] = sanitize_data_for_logging(value)
        # Process lists of items
        elif isinstance(value, list):
            sanitized[key] = [sanitize_data_for_logging(item) for item in value]
        # Pass through other values
        else:
            sanitized[key] = value
            
    return sanitized

def ensure_directories():
    """Ensure all required directories exist.
    
    Returns:
        bool: True if all directories were created successfully, False otherwise
    """
    required_folders = [
        config.DATA_FOLDER,
        config.VALIDATED_FOLDER, 
        config.RETURNS_FOLDER,
        config.LOGS_FOLDER, 
        config.PROCESSING_FOLDER
    ]
    
    try:
        for folder in required_folders:
            os.makedirs(folder, exist_ok=True)
        return True
    except Exception as e:
        error_logger.error(f"Failed to create directories: {e}")
        return False

def cleanup_processing_folder():
    """Clean up any files left in the processing folder from previous runs.
    
    Returns:
        int: Number of files moved from processing to returns folder
    """
    moved_count = 0
    try:
        for file in os.listdir(config.PROCESSING_FOLDER):
            file_path = os.path.join(config.PROCESSING_FOLDER, file)
            if os.path.isfile(file_path):
                try:
                    # Move any files in processing to returns as they were interrupted
                    shutil.move(file_path, os.path.join(config.RETURNS_FOLDER, file))
                    logging.getLogger('app').warning(f"Moved interrupted processing file to returns: {file}")
                    moved_count += 1
                except (PermissionError, OSError) as e:
                    error_logger.error(f"Could not move interrupted file {file}: {str(e)}")
    except Exception as e:
        error_logger.error(f"Error cleaning processing folder: {str(e)}")
    
    return moved_count