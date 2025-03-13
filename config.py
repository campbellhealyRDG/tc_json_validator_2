"""Configuration module for JSON processor application."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Application settings
DEBUG = os.environ.get("DEBUG", "False").lower() in ["true", "1", "yes"]

# Folder paths
DATA_FOLDER = os.environ.get("DATA_FOLDER", "data")
VALIDATED_FOLDER = os.environ.get("VALIDATED_FOLDER", "validated")
RETURNS_FOLDER = os.environ.get("RETURNS_FOLDER", "returns")
LOGS_FOLDER = os.environ.get("LOGS_FOLDER", "logs")
PROCESSING_FOLDER = os.environ.get("PROCESSING_FOLDER", "processing")

# Email configuration
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "noreply@example.com")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "admin@example.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# System requirements
MIN_DISK_SPACE_MB = 100  # Minimum required free disk space in MB
REQUIRED_ENV_VARS = ["EMAIL_PASSWORD"]

# Retry settings
FILE_ACCESS_MAX_ATTEMPTS = 10
FILE_ACCESS_DELAY = 1
FILE_MOVE_MAX_ATTEMPTS = 3
THIRD_PARTY_MAX_RETRIES = 3