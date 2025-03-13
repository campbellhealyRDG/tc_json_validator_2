import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Turn Debugging Off (False) or On (True)
DEBUG = False  # Set to True to enable debugging

# Define folder paths
DATA_FOLDER = "data"
VALIDATED_FOLDER = "validated"
RETURNS_FOLDER = "returns"
LOGS_FOLDER = "logs"
PROCESSING_FOLDER = "processing"  # Temporary folder for files being processed

# Logging configuration
APP_LOG_PATH = os.path.join(LOGS_FOLDER, 'app.log')
ERROR_LOG_PATH = os.path.join(LOGS_FOLDER, 'error.log')
DEBUG_LOG_PATH = os.path.join(LOGS_FOLDER, 'debug.log')

# Email configuration
SENDER_EMAIL = os.environ.get("EMAIL_SENDER", "noreply@example.com")
RECEIVER_EMAIL = os.environ.get("EMAIL_RECEIVER", "admin@example.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")  # Get from environment variable
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))  # Use 587 for Office 365

# File processing settings
MAX_FILE_ACCESS_ATTEMPTS = 10
FILE_ACCESS_DELAY = 1
FILE_MOVE_MAX_ATTEMPTS = 3
FILE_MOVE_RETRY_DELAY = 1

# Third-party API settings
THIRD_PARTY_MAX_RETRIES = 3
THIRD_PARTY_BACKOFF_BASE = 2  # For exponential backoff

# System requirements
MIN_PYTHON_VERSION = (3, 7)
MIN_FREE_DISK_SPACE_MB = 100  # Minimum free disk space in MB

# Required environment variables
REQUIRED_ENV_VARS = ["EMAIL_PASSWORD"]