import os
import json
import time
import shutil
import uuid
import logging
import signal
import sys
import traceback
from logging.handlers import RotatingFileHandler
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, ValidationError, Field, SecretStr
from watchdog.observers.polling import PollingObserver  # More compatible observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logging.debug("Script has started running...")
print("Script is running...")

# Define folder paths
data_folder = "data"
validated_folder = "validated"
returns_folder = "returns"
logs_folder = "logs"
processing_folder = "processing"  # Temporary folder for files being processed

# Ensure output directories exist
for folder in [validated_folder, returns_folder, logs_folder, processing_folder]:
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        print(f"CRITICAL: Cannot create {folder} directory: {str(e)}")
        sys.exit(1)

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
    # Use SecretStr for sensitive data - adds a layer of protection for card numbers
    CustomerCardNumber: SecretStr = Field(..., min_length=16, max_length=16)

class JSONFileHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.processing_files = set()  # Track files being processed to avoid duplicates
    
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".json"):
            file_path = os.path.abspath(event.src_path)
            self.process_file(file_path)

    def process_file(self, file_path):
        """Process a JSON file with improved error handling and safety."""
        # Skip if already processing this file
        if file_path in self.processing_files:
            debug_logger.debug(f"Already processing {file_path}, skipping")
            return
        
        self.processing_files.add(file_path)
        debug_logger.debug(f"New file detected: {file_path}")
        file_name = os.path.basename(file_path)
        unique_id = str(uuid.uuid4())[:8]
        new_file_name = f"{unique_id}_{file_name}"
        processing_path = os.path.join(processing_folder, new_file_name)
        
        try:
            # Wait for file to be completely written and check access
            success = self.wait_for_file_access(file_path, max_attempts=10)
            if not success:
                error_logger.error(f"Cannot access file after multiple attempts: {file_path}")
                self.processing_files.remove(file_path)
                return
            
            # Move to processing folder first to avoid conflicts
            try:
                shutil.copy2(file_path, processing_path)
                debug_logger.debug(f"Copied file to processing folder: {processing_path}")
                
                # Only remove original if copy successful
                try:
                    os.remove(file_path)
                    debug_logger.debug(f"Removed original file: {file_path}")
                except (PermissionError, OSError) as e:
                    error_logger.error(f"Unable to remove original file {file_path}: {str(e)}")
            except (PermissionError, OSError) as e:
                error_logger.error(f"Failed to copy file to processing folder: {str(e)}")
                self.processing_files.remove(file_path)
                return
            
            # Process from the processing folder
            try:
                with open(processing_path, 'r') as file:
                    debug_logger.debug(f"Reading file content: {processing_path}")
                    try:
                        data = json.load(file)
                    except json.JSONDecodeError as je:
                        error_msg = f"Invalid JSON format in {file_name}: {str(je)}"
                        error_logger.error(error_msg)
                        self.move_file(processing_path, returns_folder, new_file_name)
                        self.send_error_email(new_file_name, error_msg)
                        return
                
                validation_result = self.validate_json(data)
                if validation_result is True:
                    self.move_file(processing_path, validated_folder, new_file_name)
                    app_logger.info(f"Validated: {new_file_name}")
                    self.send_to_third_party(os.path.join(validated_folder, new_file_name))
                else:
                    error_msg = f"Invalid JSON structure: {validation_result}"
                    self.move_file(processing_path, returns_folder, new_file_name)
                    app_logger.warning(f"Invalid file {new_file_name}: {error_msg}")
                    self.send_error_email(new_file_name, error_msg)
            except Exception as e:
                stack_trace = traceback.format_exc()
                error_msg = f"Error processing {file_name}: {str(e)}"
                error_logger.error(f"{error_msg}\n{stack_trace}")
                self.move_file(processing_path, returns_folder, new_file_name)
                self.send_error_email(new_file_name, f"{error_msg}\n\nStack trace:\n{stack_trace}")
        finally:
            # Clean up processing folder and tracking set
            self.processing_files.remove(file_path)
            if os.path.exists(processing_path):
                try:
                    os.remove(processing_path)
                    debug_logger.debug(f"Cleaned up processing file: {processing_path}")
                except (PermissionError, OSError) as e:
                    error_logger.error(f"Failed to clean up processing file {processing_path}: {str(e)}")
    
    def wait_for_file_access(self, file_path, max_attempts=5, delay=1):
        """Wait for a file to be accessible with multiple retries."""
        for attempt in range(max_attempts):
            if not os.path.exists(file_path):
                debug_logger.debug(f"File does not exist yet (attempt {attempt+1}): {file_path}")
                time.sleep(delay)
                continue
                
            try:
                # Try to open the file to ensure it's not locked
                with open(file_path, 'rb') as f:
                    # Read a small amount to check if file is accessible
                    f.read(1)
                return True
            except (PermissionError, OSError) as e:
                debug_logger.debug(f"File not accessible yet (attempt {attempt+1}): {str(e)}")
                time.sleep(delay)
        
        return False
    
    def move_file(self, source_path, dest_folder, filename):
        """Safely move a file to destination folder with retries."""
        dest_path = os.path.join(dest_folder, filename)
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                # Check if destination exists and handle it
                if os.path.exists(dest_path):
                    alternative_name = f"{str(uuid.uuid4())[:8]}_{filename}"
                    dest_path = os.path.join(dest_folder, alternative_name)
                    debug_logger.debug(f"Destination exists, using alternative name: {alternative_name}")
                
                shutil.copy2(source_path, dest_path)
                debug_logger.debug(f"Successfully moved file to {dest_path}")
                return True
            except (PermissionError, OSError) as e:
                error_logger.error(f"Failed to move file on attempt {attempt+1}: {str(e)}")
                time.sleep(1)
        
        error_logger.error(f"Failed to move file after {max_attempts} attempts: {source_path}")
        return False

    def validate_json(self, data):
        """Check if JSON follows the required structure using Pydantic."""
        debug_logger.debug(f"Validating JSON data: {data}")
        try:
            # Create a copy of data with masked card number for logging
            safe_log_data = data.copy()
            if 'CustomerCardNumber' in safe_log_data:
                card_num = safe_log_data['CustomerCardNumber']
                if len(card_num) >= 8:
                    # Only log last 4 digits, mask the rest
                    safe_log_data['CustomerCardNumber'] = '*' * (len(card_num) - 4) + card_num[-4:]
                else:
                    safe_log_data['CustomerCardNumber'] = '****'
            debug_logger.debug(f"Validating JSON data: {safe_log_data}")
            
            JSONSchema(**data)
            return True
        except ValidationError as e:
            return e.errors()

    def send_to_third_party(self, file_path):
        """Simulate sending the file to a 3rd party."""
        app_logger.info(f"Sending {os.path.basename(file_path)} to 3rd party")
        debug_logger.debug(f"Full path for 3rd party transmission: {file_path}")
        # Add actual code to send the file to the 3rd party (e.g., via HTTP API or FTP)
        
        # Retry mechanism for external API calls would be added here
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Simulate API call
                # third_party_api.send_file(file_path)
                time.sleep(0.1)  # Simulate processing
                debug_logger.debug(f"Successfully sent file to third party")
                return True
            except Exception as e:
                error_logger.error(f"Failed to send to third party (attempt {attempt+1}): {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
                
        error_logger.error(f"Failed to send file to third party after {max_retries} attempts")
        return False
    
    def send_error_email(self, file_name, error_message):
        """Send an email notification to the admin using secure connection."""
        app_logger.info(f"Sending error email about {file_name}")
        debug_logger.debug(f"Email error details: {error_message}")
        
        # Prepare the email content
        subject = f"File Validation Error: {file_name}"
        body = f"The file {file_name} failed validation.\n\nError: {error_message}\n\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Email setup from environment variables
        sender_email = os.environ.get("EMAIL_SENDER", "noreply@example.com")
        receiver_email = os.environ.get("EMAIL_RECEIVER", "admin@example.com")
        password = os.environ.get("EMAIL_PASSWORD", "")  # Get from environment variable
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.example.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))  # Default to secure port
        
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
            # Use secure context for email
            context = ssl.create_default_context()
            
            # Connect securely to SMTP server (using SSL)
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(sender_email, password)
                text = msg.as_string()
                server.sendmail(sender_email, receiver_email, text)
                app_logger.info(f"Error email sent to {receiver_email}")
        except Exception as e:
            stack_trace = traceback.format_exc()
            error_logger.error(f"Failed to send email: {str(e)}\n{stack_trace}")

# Global variables for graceful shutdown
observer = None
running = True

def signal_handler(sig, frame):
    """Handle termination signals for graceful shutdown."""
    global running
    app_logger.info(f"Received signal {sig}, shutting down gracefully...")
    running = False

def check_system_requirements():
    """Check if system meets requirements to run the application."""
    try:
        # Check Python version
        if sys.version_info < (3, 7):
            error_logger.critical("Python 3.7 or higher is required")
            return False
        
        # Check disk space
        if os.name == 'posix':  # Linux/Unix/MacOS
            import shutil
            total, used, free = shutil.disk_usage("/")
            if free < 100 * 1024 * 1024:  # Less than 100 MB free
                error_logger.critical(f"Low disk space: {free / (1024 * 1024):.2f} MB free")
                return False
        
        # Check folder permissions
        for folder in [data_folder, validated_folder, returns_folder, logs_folder, processing_folder]:
            if not os.access(folder, os.R_OK | os.W_OK):
                error_logger.critical(f"Insufficient permissions for folder '{folder}'. Need read/write access.")
                return False
        
        # Check that required environment variables are set
        required_env_vars = ["EMAIL_PASSWORD"]
        missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
        if missing_vars:
            error_logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}")
            error_logger.info("Please create a .env file with the required variables or set them in your environment")
            return False
        
        return True
    except Exception as e:
        stack_trace = traceback.format_exc()
        error_logger.critical(f"Error checking system requirements: {str(e)}\n{stack_trace}")
        return False

def run_file_processor():
    """Main function to run the file processor with proper setup and error handling."""
    global observer, running
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Handles Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Handles termination signal
    if hasattr(signal, 'SIGHUP'):  # Not available on Windows
        signal.signal(signal.SIGHUP, signal_handler)  # Handles terminal close
    
    app_logger.info("Starting Customer JSON Processor")
    debug_logger.debug(f"Working directory: {os.getcwd()}")
    
    # Check system requirements
    if not check_system_requirements():
        error_logger.critical("System requirements check failed. Exiting.")
        return 1
    
    # Validate data directory exists and is accessible
    if not os.path.isdir(data_folder):
        app_logger.warning(f"Data folder '{data_folder}' does not exist. Creating it.")
        try:
            os.makedirs(data_folder, exist_ok=True)
        except PermissionError:
            error_logger.critical(f"Cannot create data folder '{data_folder}'. Check permissions.")
            return 1
    
    # Clean up processing folder at startup
    try:
        for file in os.listdir(processing_folder):
            file_path = os.path.join(processing_folder, file)
            if os.path.isfile(file_path):
                try:
                    # Move any files in processing to returns as they were interrupted
                    shutil.move(file_path, os.path.join(returns_folder, file))
                    app_logger.warning(f"Moved interrupted processing file to returns: {file}")
                except (PermissionError, OSError) as e:
                    error_logger.error(f"Could not move interrupted file {file}: {str(e)}")
    except Exception as e:
        error_logger.error(f"Error cleaning processing folder: {str(e)}")
    
    # Set up file event handler
    event_handler = JSONFileHandler()
    observer = PollingObserver()  # Using PollingObserver for better cross-platform compatibility
    observer.schedule(event_handler, data_folder, recursive=False)
    
    try:
        observer.start()
        app_logger.info(f"Watching folder: {data_folder}")
        debug_logger.debug("Observer started successfully")
        
        # Process any existing files in the data folder
        for file in os.listdir(data_folder):
            if file.endswith('.json'):
                file_path = os.path.join(data_folder, file)
                if os.path.isfile(file_path):
                    app_logger.info(f"Processing existing file at startup: {file}")
                    event_handler.process_file(file_path)
        
        # Main loop with proper termination
        while running:
            time.sleep(1)
            
            # Add periodic health checks
            if observer is None or not observer.is_alive():
                error_logger.critical("Observer has died unexpectedly. Restarting...")
                observer = PollingObserver()
                observer.schedule(event_handler, data_folder, recursive=False)
                observer.start()
    except KeyboardInterrupt:
        app_logger.info("Process terminated by user")
    except Exception as e:
        stack_trace = traceback.format_exc()
        error_logger.critical(f"Unhandled exception: {str(e)}\n{stack_trace}")
        return 1
    finally:
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=5)  # Wait up to 5 seconds for the observer to stop
                app_logger.info("Observer stopped successfully")
            except Exception as e:
                error_logger.error(f"Error stopping observer: {str(e)}")
        
        app_logger.info("Application shutdown complete")
    
    return 0

if __name__ == "__main__":
    exit_code = run_file_processor()
    sys.exit(exit_code)