# Customer JSON Processor

## Overview
This script is designed to process and validate JSON files containing customer data. It watches a specified directory for new JSON files, processes them, and validates their structure. The script uses Pydantic models for schema validation and sanitises sensitive information for logging purposes. After processing, the valid files are moved to a validated folder, while invalid ones are moved to a returns folder, and error notifications are sent to the administrators via email.

## Features

- **File Watcher**: Monitors a specified folder for new JSON files.
- **File Processing**: Reads and processes the JSON files, ensuring they conform to the specified schema.
- **Logging**: Uses a robust logging system that captures detailed logs for debugging, application information, and error reporting.
- **Email Notifications**: Sends an email notification when a file fails validation.
- **Directory Management**: Automatically creates necessary folders if they don't exist.
- **Graceful Shutdown**: Handles termination signals (Ctrl+C, SIGTERM) gracefully.
- **Environment Variables**: Loads configuration from a `.env` file to handle sensitive data securely.
  
## Requirements

- Python 3.7+
- Required Python packages:
  - `pydantic`
  - `watchdog`
  - `python-dotenv`
  
Use `pip` to install the dependencies:
```bash
pip install pydantic watchdog python-dotenv
```

## Setup

1. **Create a `.env` File**: 
   Ensure that a `.env` file exists with the following variables:
   ```env
   EMAIL_SENDER="your-email@example.com"
   EMAIL_RECEIVER="admin-email@example.com"
   EMAIL_PASSWORD="your-email-password"
   SMTP_SERVER="smtp.example.com"
   SMTP_PORT=587
   ```

2. **Directory Structure**: 
   The script expects the following directories to exist or be created automatically:
   - `data` – the folder where the incoming JSON files will be placed.
   - `validated` – the folder where successfully validated files are moved.
   - `returns` – the folder where invalid files are moved.
   - `logs` – the folder where log files are stored.
   - `processing` – the temporary folder where files are held while they are being processed.

## Script Flow

1. **Initialization**: 
   The script sets up logging, directories, and environment variables. It checks the system requirements such as disk space, folder permissions, and environment variables.
   
2. **File Watcher**: 
   Using `watchdog`, the script monitors the `data` folder for new files. When a new JSON file is detected, it begins processing.

3. **Processing a File**: 
   - The file is copied to the `processing` folder to avoid conflicts.
   - The file is then validated against a Pydantic model.
   - If the file is valid, it is moved to the `validated` folder. If invalid, it is moved to the `returns` folder, and an error email is sent.
   - Sensitive data like card numbers is masked in the logs to ensure privacy.

4. **Graceful Shutdown**: 
   The script can handle termination signals to cleanly stop the file watcher and any ongoing processing.

5. **Error Handling**: 
   Errors during processing are logged with stack traces, and email notifications are sent for critical errors.

## How to Run

To run the script, simply execute the Python file:

```bash
python customer_json_processor.py
```

The script will:
- Start watching the `data` folder.
- Process any existing JSON files in the `data` folder at startup.
- Continuously monitor and process new files added to the folder.

## Logging

The script logs events to the following log files:
- `logs/app.log`: General application logs.
- `logs/error.log`: Logs of errors.
- `logs/debug.log`: Detailed logs for debugging.

It also outputs logs to the console.

### Log Levels:
- **INFO**: General information about the running script.
- **DEBUG**: Detailed debugging information (only enabled if `DEBUG = True`).
- **ERROR**: Error messages for failures.

## Error Notifications

If a file fails validation, an email is sent to the administrator (as defined in the `.env` file). The email includes:
- The file name.
- A description of the error.
- A timestamp of when the error occurred.

## Graceful Shutdown

To gracefully stop the script, you can send a termination signal such as `Ctrl+C`. The script will clean up, stop the file observer, and shut down properly.

## Conclusion

This script is an efficient tool for handling and validating customer data in JSON format. It ensures that all data is processed, validated, and securely logged, making it an essential utility for data pipelines.