# main.py
"""Main entry point for the JSON processor application."""
import os
import sys
import time
import signal
import logging
import traceback
from watchdog.observers.polling import PollingObserver

# Application modules
import config
from logger import setup_logging
from handlers.file_handler import JSONFileHandler
from utils.validators import check_system_requirements
from utils.file_operations import ensure_directories, cleanup_processing_folder

# Global variables for graceful shutdown
observer = None
running = True

def signal_handler(sig, frame):
    """Handle termination signals for graceful shutdown."""
    global running
    logging.getLogger('app').info(f"Received signal {sig}, shutting down gracefully...")
    running = False

def process_existing_files(event_handler):
    """Process any existing files in the data folder.
    
    Args:
        event_handler: The file handler to use for processing
    
    Returns:
        int: Number of files processed
    """
    count = 0
    for file in os.listdir(config.DATA_FOLDER):
        if file.endswith('.json'):
            file_path = os.path.join(config.DATA_FOLDER, file)
            if os.path.isfile(file_path):
                logging.getLogger('app').info(f"Processing existing file at startup: {file}")
                event_handler.process_file(file_path)
                count += 1
    return count

def run_file_processor():
    """Main function to run the file processor with proper setup and error handling."""
    global observer, running
    
    # Set up logging
    loggers = setup_logging()
    app_logger = loggers['app']
    error_logger = loggers['error']
    debug_logger = loggers['debug']
    
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
    
    # Ensure all directories exist
    if not ensure_directories():
        error_logger.critical("Failed to create required directories. Exiting.")
        return 1
    
    # Clean up processing folder at startup
    cleanup_count = cleanup_processing_folder()
    if cleanup_count > 0:
        app_logger.info(f"Cleaned up {cleanup_count} interrupted files from previous run")
    
    # Set up file event handler
    event_handler = JSONFileHandler()
    observer = PollingObserver()  # Using PollingObserver for better cross-platform compatibility
    observer.schedule(event_handler, config.DATA_FOLDER, recursive=False)
    
    try:
        observer.start()
        app_logger.info(f"Watching folder: {config.DATA_FOLDER}")
        debug_logger.debug("Observer started successfully")
        
        # Process any existing files in the data folder
        processed_count = process_existing_files(event_handler)
        if processed_count > 0:
            app_logger.info(f"Processed {processed_count} existing files at startup")
        
        # Main loop with proper termination
        while running:
            time.sleep(1)
            
            # Add periodic health checks
            if observer is None or not observer.is_alive():
                error_logger.critical("Observer has died unexpectedly. Restarting...")
                observer = PollingObserver()
                observer.schedule(event_handler, config.DATA_FOLDER, recursive=False)
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