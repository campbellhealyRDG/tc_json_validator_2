"""File processing logic for the JSON processor application."""
import os
import json
import uuid
import logging
import traceback
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

class JSONFileHandler(FileSystemEventHandler):
    """Handler for processing JSON files."""
    
    def __init__(self):
        super().__init__()
        self.processing_files = set()  # Track files being processed to avoid duplicates
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        if event.src_path.endswith(".json"):
            file_path = os.path.abspath(event.src_path)
            self.process_file(file_path)

    def process_file(self, file_path):
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
        
        self.processing_files.add(file_path)
        debug_logger.debug(f"New file detected: {file_path}")
        file_name = os.path.basename(file_path)
        unique_id = str(uuid.uuid4())[:8]
        new_file_name = f"{unique_id}_{file_name}"
        processing_path = os.path.join(config.PROCESSING_FOLDER, new_file_name)
        
        try:
            # Wait for file to be completely written and check access
            success = wait_for_file_access(file_path)
            if not success:
                error_logger.error(f"Cannot access file after multiple attempts: {file_path}")
                self.processing_files.discard(file_path)
                return False
            
            # Move to processing folder first to avoid conflicts
            try:
                # Copy file to processing folder
                with open(file_path, 'rb') as src_file:
                    with open(processing_path, 'wb') as dest_file:
                        dest_file.write(src_file.read())
                debug_logger.debug(f"Copied file to processing folder: {processing_path}")
                
                # Only remove original if copy successful
                try:
                    os.remove(file_path)
                    debug_logger.debug(f"Removed original file: {file_path}")
                except (PermissionError, OSError) as e:
                    error_logger.error(f"Unable to remove original file {file_path}: {str(e)}")
            except (PermissionError, OSError) as e:
                error_logger.error(f"Failed to copy file to processing folder: {str(e)}")
                self.processing_files.discard(file_path)
                return False
            
            # Process from the processing folder
            return self._process_json_file(processing_path, new_file_name)
            
        finally:
            # Clean up processing folder and tracking set
            self.processing_files.discard(file_path)
            if os.path.exists(processing_path):
                try:
                    os.remove(processing_path)
                    debug_logger.debug(f"Cleaned up processing file: {processing_path}")
                except (PermissionError, OSError) as e:
                    error_logger.error(f"Failed to clean up processing file {processing_path}: {str(e)}")

    def _process_json_file(self, file_path, file_name):
        """Process the JSON file content.
        
        Args:
            file_path: Path to the JSON file in the processing folder
            file_name: Name of the file with unique ID prefix
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            with open(file_path, 'r') as file:
                debug_logger.debug(f"Reading file content: {file_path}")
                try:
                    data = json.load(file)
                except json.JSONDecodeError as je:
                    error_msg = f"Invalid JSON format in {file_name}: {str(je)}"
                    error_logger.error(error_msg)
                    move_file(file_path, config.RETURNS_FOLDER, file_name)
                    send_error_email(file_name, error_msg)
                    return False
            
            # Log the structure type for debugging
            is_nested = 'Customer' in data and isinstance(data['Customer'], dict)
            structure_type = "nested" if is_nested else "flat"
            debug_logger.debug(f"Detected {structure_type} JSON structure in {file_name}")
            
            # Create sanitized data for logging (mask sensitive information)
            sanitized_data = sanitize_data_for_logging(data)
            debug_logger.debug(f"Processing data: {sanitized_data}")
            
            validation_result = self.validate_json(data)
            if validation_result is True:
                move_file(file_path, config.VALIDATED_FOLDER, file_name)
                app_logger.info(f"Validated {structure_type} JSON: {file_name}")
                validated_file_path = os.path.join(config.VALIDATED_FOLDER, file_name)
                send_to_third_party(validated_file_path)
                return True
            else:
                error_msg = f"Invalid JSON structure: {validation_result}"
                move_file(file_path, config.RETURNS_FOLDER, file_name)
                app_logger.warning(f"Invalid file {file_name}: {error_msg}")
                send_error_email(file_name, error_msg)
                return False
                
        except Exception as e:
            stack_trace = traceback.format_exc()
            error_msg = f"Error processing {file_name}: {str(e)}"
            error_logger.error(f"{error_msg}\n{stack_trace}")
            move_file(file_path, config.RETURNS_FOLDER, file_name)
            send_error_email(file_name, f"{error_msg}\n\nStack trace:\n{stack_trace}")
            return False

    def validate_json(self, data):
        """Check if JSON follows the required structure using Pydantic.
        
        Args:
            data: JSON data to validate
            
        Returns:
            True if valid, error details if invalid
        """
        debug_logger.debug(f"Validating JSON data structure")
        try:
            # Validate against our schema
            JSONSchema(**data)
            return True
        except ValidationError as e:
            return e.errors()