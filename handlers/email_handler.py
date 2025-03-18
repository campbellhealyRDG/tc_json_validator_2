"""Email notification functionality for the JSON processor application."""
import smtplib
import ssl
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import lru_cache

import config

# Get loggers
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
debug_logger = logging.getLogger('debug')


@lru_cache(maxsize=1)
def get_ssl_context():
    """Create and cache SSL context to avoid recreating it for each email."""
    return ssl.create_default_context()


def send_error_email(file_name, error_message):
    """Send an email notification to the admin using secure connection.
   
    Args:
        file_name: Name of the file with an error
        error_message: Error message details
       
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    app_logger.info(f"Sending error email about {file_name}")
    debug_logger.debug(f"Email error details: {error_message}")
   
    # Email setup from config
    sender_email = config.EMAIL_SENDER
    receiver_email = config.EMAIL_RECEIVER
    password = config.EMAIL_PASSWORD
    smtp_server = config.SMTP_SERVER
    smtp_port = config.SMTP_PORT
   
    if not all([sender_email, receiver_email, password, smtp_server, smtp_port]):
        error_logger.error("Email configuration missing required values")
        return False
       
    # Create the email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"File Validation Error: {file_name}"
    
    # Prepare the email body
    body = (f"The file {file_name} failed validation.\n\n"
            f"Error: {error_message}\n\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    msg.attach(MIMEText(body, 'plain'))
   
    try:
        # Get cached SSL context
        context = get_ssl_context()
       
        # Connect to SMTP server and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender_email, password)
            server.send_message(msg)
            app_logger.info(f"Error email sent to {receiver_email}")
            return True
            
    except Exception as e:
        error_logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        return False