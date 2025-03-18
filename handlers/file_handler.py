"""File processing logic for the JSON processor application."""
import os
import json
import uuid
import logging
from contextlib import contextmanager
from typing import Optional, Tuple, Union

from pydantic import ValidationError
from watchdog.events import FileSystemEventHandler

from models.schemas import JSONSchema
from utils.file_operations import wait_for_file_access, move_file, sanitize_data_for_logging
from handlers.email_handler import send_error_email
from handlers.third_party import send_to_third_party
import config

# Get loggers
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
debug_logger = logging.getLogger('debug')


@contextmanager
def track_processing(handler, file_path):
    """Context manager to track file processing and ensure cleanup.
    
    Args:
        handler: The file handler instance
        file_path: Path to the file being processed
    """
    try:
        handler.processing_files.add(file_path)
        yield
    finally:
        handler.processing_files.discard(file_path)


def safe_file_copy(source_path: str, dest_path: str) -> bool:
    """Safely copy a file and optionally remove the original.
    
    Args:
        source_path: Path to the source file
        dest_path: Path to the destination
        
    Returns:
        bool: True if operation succeeded, False otherwise
    """
    try:
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Copy file
        with open(source_path, 'rb') as src_file:
            with open(dest_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
        debug_logger.debug(f"Copied file to: {dest_path}")
        
        # Remove original
        try:
            os.remove(source_path)
            debug_logger.debug(f"Removed original file: {source_path}")
        except (PermissionError, OSError) as e:
            error_logger.error(f"Unable to remove original file {source_path}: {str(e)}")
            # Continue processing even if we couldn't remove the original
        
        return True
    except (PermissionError, OSError) as e:
        error_logger.error(f"Failed to copy file {source_path} to {dest_path}: {str(e)}")
        return False


def safe_file_cleanup(file_path: str) -> None:
    """Safely clean up a file if it exists.
    
    Args:
        file_path: Path to the file to clean up
    """
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            debug_logger.debug(f"Cleaned up file: {file_path}")
        except (PermissionError, OSError) as e:
            error_logger.error(f"Failed to clean up file {file_path}: {str(e)}")


def generate_unique_filename(original_name: str) -> str:
    """Generate a unique filename with UUID prefix.
    
    Args:
        original_name: Original filename
        
    Returns:
        str: Unique filename
    """
    unique_id = str(uuid.uuid4())[:8]
    return f"{unique_id}_{original_name}"


class JSONFileHandler(FileSystemEventHandler):
    """Handler for processing JSON files."""
    
    def __init__(self):
        super().__init__()
        self.processing_files = set()  # Track files being processed to avoid duplicates
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory or not event.src_path.endswith(".json"):
            return
            
        file_path = os.path.abspath(event.src_path)
        self.process_file(file_path)

    def process_file(self, file_path: str) -> bool:
        """Process a JSON file with improved error handling and safety.
        
        Args:
            file_path: Path to the JSON file to process
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # Skip if already processing this file
        if file_path in self.processing_files:
            debug_logger.debug(f"Already processing {file_path}, skipping")
            return False
        
        file_name = os.path.basename(file_path)
        unique_file_name = generate_unique_filename(file_name)
        processing_path = os.path.join(config.PROCESSING_FOLDER, unique_file_name)
        
        with track_processing(self, file_path):
            # Wait for file to be completely written and check access
            if not wait_for_file_access(file_path):
                error_logger.error(f"Cannot access file after multiple attempts: {file_path}")
                return False
            
            # Move to processing folder
            if not safe_file_copy(file_path, processing_path):
                return False
                
            try:
                # Process from the processing folder
                return self._process_json_file(processing_path, unique_file_name)
            finally:
                # Clean up processing folder
                safe_file_cleanup(processing_path)

    def _process_json_file(self, file_path: str, file_name: str) -> bool:
        """Process the JSON file content.
        
        Args:
            file_path: Path to the JSON file in the processing folder
            file_name: Name of the file with unique ID prefix
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            # Load and validate JSON
            data, error = self._load_json_file(file_path)
            if error:
                self._handle_error(file_path, file_name, error)
                return False
                
            # Validate data structure
            validation_result = self._validate_data(data)
            if validation_result is not True:
                error_msg = f"Invalid JSON structure: {validation_result}"
                self._handle_error(file_path, file_name, error_msg)
                return False
                
            # Process validated file
            return self._handle_valid_file(file_path, file_name, data)
                
        except Exception as e:
            error_msg = f"Error processing {file_name}: {str(e)}"
            error_logger.error(error_msg, exc_info=True)
            self._handle_error(file_path, file_name, error_msg, with_traceback=True)
            return False

    def _load_json_file(self, file_path: str) -> Tuple[Optional[dict], Optional[str]]:
        """Load and parse a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Tuple containing the parsed data (or None) and an error message (or None)
        """
        debug_logger.debug(f"Reading file content: {file_path}")
        try:
            with open(file_path, 'r') as file:
                return json.load(file), None
        except json.JSONDecodeError as je:
            error_msg = f"Invalid JSON format: {str(je)}"
            return None, error_msg
        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            return None, error_msg
    
    def _validate_data(self, data: dict) -> Union[bool, list]:
        """Validate JSON data against schema.
        
        Args:
            data: The JSON data to validate
            
        Returns:
            True if valid, error details if invalid
        """
        # Log data structure type
        is_nested = 'Customer' in data and isinstance(data['Customer'], dict)
        structure_type = "nested" if is_nested else "flat"
        debug_logger.debug(f"Detected {structure_type} JSON structure")
        
        # Log sanitized data for debugging
        sanitized_data = sanitize_data_for_logging(data)
        debug_logger.debug(f"Processing data: {sanitized_data}")
        
        # Validate against schema
        try:
            JSONSchema(**data)
            return True
        except ValidationError as e:
            return e.errors()
    
    def _handle_valid_file(self, file_path: str, file_name: str, data: dict) -> bool:
        """Handle a valid JSON file.
        
        Args:
            file_path: Path to the JSON file
            file_name: Name of the file
            data: The validated JSON data
            
        Returns:
            bool: True if handling succeeded
        """
        validated_path = os.path.join(config.VALIDATED_FOLDER, file_name)
        
        # Move to validated folder
        if not move_file(file_path, config.VALIDATED_FOLDER, file_name):
            error_logger.error(f"Failed to move file to validated folder: {file_name}")
            return False
            
        # Log success
        structure_type = "nested" if 'Customer' in data and isinstance(data['Customer'], dict) else "flat"
        app_logger.info(f"Validated {structure_type} JSON: {file_name}")
        
        # Send to third party
        return send_to_third_party(validated_path)
    
    def _handle_error(self, file_path: str, file_name: str, error_msg: str, with_traceback: bool = False) -> None:
        """Handle file processing errors.
        
        Args:
            file_path: Path to the JSON file
            file_name: Name of the file
            error_msg: Error message
            with_traceback: Whether to include traceback in email
        """
        # Move to returns folder
        move_file(file_path, config.RETURNS_FOLDER, file_name)
        
        # Log error
        app_logger.warning(f"Invalid file {file_name}: {error_msg}")
        
        # Send email notification
        email_msg = error_msg
        if with_traceback:
            email_msg = f"{error_msg}\n\nCheck logs for stack trace."
            
        send_error_email(file_name, email_msg)