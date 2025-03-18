"""Email notification functionality for the JSON processor application."""
import os
import time
import smtplib
import ssl
import traceback
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config

# Get loggers
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
debug_logger = logging.getLogger('debug')

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
    
    # Prepare the email content
    subject = f"File Validation Error: {file_name}"
    body = f"The file {file_name} failed validation.\n\nError: {error_message}\n\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Email setup from environment variables
    sender_email = config.EMAIL_SENDER
    receiver_email = config.EMAIL_RECEIVER
    password = config.EMAIL_PASSWORD
    smtp_server = config.SMTP_SERVER
    smtp_port = config.SMTP_PORT
    
    if not password:
        error_logger.error("Email password not set in environment variables")
        return False
        
    # Create the email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Create secure context
        context = ssl.create_default_context()
        
        # Connect to SMTP server and then upgrade with STARTTLS
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()  # Can be omitted
            server.starttls(context=context)  # Secure the connection
            server.ehlo()  # Can be omitted
            server.login(sender_email, password)
            text = msg.as_string()
            server.sendmail(sender_email, receiver_email, text)
            app_logger.info(f"Error email sent to {receiver_email}")
            return True
    except Exception as e:
        stack_trace = traceback.format_exc()
        error_logger.error(f"Failed to send email: {str(e)}\n{stack_trace}")
        return False