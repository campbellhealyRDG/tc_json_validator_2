import os
import json
import time
import shutil
import uuid
import logging
from logging.handlers import RotatingFileHandler
import smtplib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import BaseModel, ValidationError, Field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Define folder paths
data_folder = "data"
validated_folder = "validated"
returns_folder = "returns"
logs_folder = "logs"

# Ensure output directories exist
os.makedirs(validated_folder, exist_ok=True)
os.makedirs(returns_folder, exist_ok=True)
os.makedirs(logs_folder, exist_ok=True)

# Set up log file paths
app_log_path = os.path.join(logs_folder, 'app.log')
error_log_path = os.path.join(logs_folder, 'error.log')
debug_log_path = os.path.join(logs_folder, 'debug.log')

# Enhanced log formatter with filename and line numbers
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s'
)
simple_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Capture all levels for the root logger

# 1. App Logger (INFO level)
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.INFO)
# Rotating file handler for app logs - 5MB max size, keep 5 backup files
app_handler = RotatingFileHandler(
    app_log_path, maxBytes=5*1024*1024, backupCount=5
)
app_handler.setFormatter(simple_formatter)
app_handler.setLevel(logging.INFO)
app_logger.addHandler(app_handler)

# 2. Error Logger (ERROR level)
error_logger = logging.getLogger('error')
error_logger.setLevel(logging.ERROR)
# Rotating file handler for error logs - 2MB max size, keep 10 backup files
error_handler = RotatingFileHandler(
    error_log_path, maxBytes=2*1024*1024, backupCount=10
)
error_handler.setFormatter(detailed_formatter)
error_handler.setLevel(logging.ERROR)
error_logger.addHandler(error_handler)

# 3. Debug Logger (DEBUG level)
debug_logger = logging.getLogger('debug')
debug_logger.setLevel(logging.DEBUG)
# Rotating file handler for debug logs - 10MB max size, keep 3 backup files
debug_handler = RotatingFileHandler(
    debug_log_path, maxBytes=10*1024*1024, backupCount=3
)
debug_handler.setFormatter(detailed_formatter)
debug_handler.setLevel(logging.DEBUG)
debug_logger.addHandler(debug_handler)

# Console handler for important messages (INFO and above)
console_handler = logging.StreamHandler()
console_handler.setFormatter(simple_formatter)
console_handler.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

class JSONSchema(BaseModel):
    OperatorID: str = Field(..., min_length=5, pattern=r"^[a-zA-Z0-9]+$")
    CustomerID: str = Field(..., min_length=7)
    CustomerCardNumber: str = Field(..., min_length=16, max_length=16)

class JSONFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".json"):
            self.process_file(event.src_path)

    def process_file(self, file_path):
        debug_logger.debug(f"New file detected: {file_path}")
        time.sleep(1)  # Ensure file is fully written before reading
        
        file_name = os.path.basename(file_path)
        unique_id = str(uuid.uuid4())[:8]
        new_file_name = f"{unique_id}_{file_name}"
        
        # Check file existence and permissions
        if not self.check_file_access(file_path):
            error_logger.error(f"Cannot access file {file_path}. Skipping.")
            return
        
        try:
            with open(file_path, 'r') as file:
                debug_logger.debug(f"Reading file content: {file_path}")
                try:
                    data = json.load(file)
                except json.JSONDecodeError as je:
                    error_msg = f"Invalid JSON format in {file_name}: {str(je)}"
                    error_logger.error(error_msg)
                    self.move_to_returns(file_path, new_file_name, error_msg)
                    return
            
            validation_result = self.validate_json(data)
            if validation_result is True:
                self.move_to_validated(file_path, new_file_name)
                self.send_to_third_party(os.path.join(validated_folder, new_file_name))
            else:
                error_msg = f"Invalid JSON structure: {validation_result}"
                self.move_to_returns(file_path, new_file_name, error_msg)
                self.send_error_email(new_file_name, error_msg)
        except Exception as e:
            error_msg = f"Unexpected error processing {file_name}: {str(e)}"
            error_logger.exception(error_msg)  # This logs the full stack trace
            self.move_to_returns(file_path, new_file_name, error_msg)
            self.send_error_email(new_file_name, error_msg)
    
    def check_file_access(self, file_path):
        """Check if file exists and we have read permissions."""
        if not os.path.exists(file_path):
            error_logger.error(f"File does not exist: {file_path}")
            return False
        if not os.access(file_path, os.R_OK):
            error_logger.error(f"No read permission for file: {file_path}")
            return False
        return True
    
    def move_to_validated(self, file_path, new_file_name):
        """Move file to validated folder."""
        destination = os.path.join(validated_folder, new_file_name)
        try:
            shutil.move(file_path, destination)
            app_logger.info(f"Validated: {new_file_name}")
            debug_logger.debug(f"File moved to {destination}")
        except (PermissionError, OSError) as e:
            error_logger.error(f"Failed to move validated file {file_path}: {str(e)}")
    
    def move_to_returns(self, file_path, new_file_name, error_msg):
        """Move file to returns folder."""
        destination = os.path.join(returns_folder, new_file_name)
        try:
            shutil.move(file_path, destination)
            app_logger.warning(f"Invalid file {new_file_name}: {error_msg}")
            debug_logger.debug(f"File moved to {destination}")
        except (PermissionError, OSError) as e:
            error_logger.error(f"Failed to move invalid file {file_path}: {str(e)}")

    def validate_json(self, data):
        """Check if JSON follows the required structure using Pydantic."""
        debug_logger.debug(f"Validating JSON data: {data}")
        try:
            JSONSchema(**data)
            return True
        except ValidationError as e:
            return e.errors()

    def send_to_third_party(self, file_path):
        """Simulate sending the file to a 3rd party."""
        app_logger.info(f"Sending {os.path.basename(file_path)} to 3rd party")
        debug_logger.debug(f"Full path for 3rd party transmission: {file_path}")
        # Add actual code to send the file to the 3rd party (e.g., via HTTP API or FTP)
    
    def send_error_email(self, file_name, error_message):
        """Simulate sending an email notification to the admin."""
        app_logger.info(f"Sending error email about {file_name}")
        debug_logger.debug(f"Email error details: {error_message}")
        
        # Prepare the email content
        subject = f"File Validation Error: {file_name}"
        body = f"The file {file_name} failed validation.\n\nError: {error_message}\n\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Email setup (this is just a simulation, you'll need to configure actual SMTP server details here)
        sender_email = "noreply@example.com"
        receiver_email = "admin@example.com"
        password = os.environ.get("EMAIL_PASSWORD", "")  # Get from environment variable
        
        if not password:
            error_logger.error("Email password not set in environment variables")
            return

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            # Simulate sending email
            debug_logger.debug(f"Connecting to SMTP server")
            with smtplib.SMTP('smtp.example.com', 587) as server:
                server.starttls()
                server.login(sender_email, password)
                text = msg.as_string()
                server.sendmail(sender_email, receiver_email, text)
                app_logger.info(f"Error email sent to {receiver_email}")
        except Exception as e:
            error_logger.error(f"Failed to send email: {str(e)}")

if __name__ == "__main__":
    app_logger.info("Starting Customer JSON Processor")
    debug_logger.debug(f"Working directory: {os.getcwd()}")
    
    # Validate data directory exists and is accessible
    if not os.path.isdir(data_folder):
        error_logger.error(f"Data folder '{data_folder}' does not exist. Creating it.")
        try:
            os.makedirs(data_folder, exist_ok=True)
        except PermissionError:
            error_logger.critical(f"Cannot create data folder '{data_folder}'. Check permissions.")
            exit(1)
    
    if not os.access(data_folder, os.R_OK | os.W_OK):
        error_logger.critical(f"Insufficient permissions for folder '{data_folder}'. Need read/write access.")
        exit(1)
    
    event_handler = JSONFileHandler()
    observer = Observer()
    observer.schedule(event_handler, data_folder, recursive=False)
    
    try:
        observer.start()
        app_logger.info(f"Watching folder: {data_folder}")
        debug_logger.debug("Observer started successfully")
        
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        app_logger.info("Process terminated by user")
        observer.stop()
    except Exception as e:
        error_logger.critical(f"Unhandled exception: {str(e)}")
        error_logger.exception("Fatal error occurred")
        observer.stop()
    finally:
        observer.join()
        app_logger.info("Application shutdown complete")