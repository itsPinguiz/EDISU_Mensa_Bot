import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Get log level from environment variable
def get_log_level():
    """Get log level from environment variable or use default"""
    level_name = os.environ.get("POLITOMENSA_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)

def setup_logger(name="PolitoMensa", log_to_file=True):
    """
    Set up and configure the logger
    
    Args:
        name: Logger name
        log_to_file: Whether to save logs to a file
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Always collect all logs at the logger level
    
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(module)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Check if we're in main terminal of dual terminal mode
    is_main_terminal = os.environ.get("POLITOMENSA_MAIN_TERMINAL") == "1"
    is_single_terminal = os.environ.get("POLITOMENSA_SINGLE_TERMINAL") == "1"
    
    # Always start with file logging first
    if log_to_file:
        # Ensure logs directory exists
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create rotating file handler with detailed logging
        log_file = os.path.join(logs_dir, f"{name}.log")
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Only add console handler if not in main terminal of dual terminal mode or if in single terminal mode
    if not is_main_terminal or is_single_terminal:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(get_log_level())
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Prevent logs from being passed to the root logger
    logger.propagate = False
    
    return logger

def get_logger(name="PolitoMensa"):
    """Get the configured logger"""
    return logging.getLogger(name)
