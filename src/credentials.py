import os
import sys
import getpass
import keyring
import dotenv
from pathlib import Path
from typing import Optional
from src.logger import get_logger

logger = get_logger("credentials")

# Service names for keyring
KEYRING_SERVICE = "PolitoMensa"
TELEGRAM_TOKEN_KEY = "telegram_token"
INSTAGRAM_USERNAME_KEY = "instagram_username"
INSTAGRAM_PASSWORD_KEY = "instagram_password"

# Load .env file if it exists
dotenv_path = Path(os.path.dirname(os.path.dirname(__file__))) / ".env"
if dotenv_path.exists():
    logger.debug(f"Loading environment from {dotenv_path}")
    dotenv.load_dotenv(dotenv_path)

def get_telegram_token() -> str:
    """
    Get the Telegram bot token from secure storage
    
    Returns:
        str: The Telegram bot token
    
    Raises:
        ValueError: If the token is not found in any storage
    """
    token = None
    
    # Try getting from keyring first
    try:
        token = keyring.get_password(KEYRING_SERVICE, TELEGRAM_TOKEN_KEY)
        if token:
            logger.debug("Retrieved Telegram token from system keyring")
    except Exception as e:
        logger.warning(f"Could not access system keyring: {str(e)}")
    
    # Fall back to environment variable
    if not token:
        token = os.environ.get("TELEGRAM_TOKEN")
        if token:
            logger.debug("Retrieved Telegram token from environment variable")
    
    if not token:
        logger.error("Telegram token not found in any secure storage")
        raise ValueError("Telegram token not found. Please set it using set_telegram_token() or TELEGRAM_TOKEN environment variable")
    
    return token

def get_instagram_credentials() -> tuple[str, str]:
    """
    Get Instagram credentials from secure storage
    
    Returns:
        tuple: (username, password)
    
    Raises:
        ValueError: If credentials are not found in any storage
    """
    username = None
    password = None
    
    # Try getting from keyring first
    try:
        username = keyring.get_password(KEYRING_SERVICE, INSTAGRAM_USERNAME_KEY)
        if username:
            password = keyring.get_password(KEYRING_SERVICE, username)
            if password:
                logger.debug("Retrieved Instagram credentials from system keyring")
    except Exception as e:
        logger.warning(f"Could not access system keyring: {str(e)}")
    
    # Fall back to environment variables
    if not username or not password:
        username = os.environ.get("INSTAGRAM_USERNAME")
        password = os.environ.get("INSTAGRAM_PASSWORD")
        if username and password:
            logger.debug("Retrieved Instagram credentials from environment variables")
    
    if not username or not password:
        logger.error("Instagram credentials not found in any secure storage")
        raise ValueError("Instagram credentials not found. Please set them using set_instagram_credentials() or environment variables")
    
    return username, password

def set_telegram_token(token: Optional[str] = None) -> bool:
    """
    Set Telegram bot token in the system keyring
    
    Args:
        token: The token to store. If None, will prompt securely.
        
    Returns:
        bool: True if successful, False otherwise
    """
    if token is None:
        token = getpass.getpass("Enter Telegram bot token: ")
    
    try:
        keyring.set_password(KEYRING_SERVICE, TELEGRAM_TOKEN_KEY, token)
        logger.info("Telegram token stored securely in system keyring")
        return True
    except Exception as e:
        logger.error(f"Failed to store Telegram token in keyring: {str(e)}")
        return False

def set_instagram_credentials(username: Optional[str] = None, password: Optional[str] = None) -> bool:
    """
    Set Instagram credentials in the system keyring
    
    Args:
        username: Instagram username. If None, will prompt.
        password: Instagram password. If None, will prompt securely.
        
    Returns:
        bool: True if successful, False otherwise
    """
    if username is None:
        username = input("Enter Instagram username: ")
    
    if password is None:
        password = getpass.getpass("Enter Instagram password: ")
    
    try:
        keyring.set_password(KEYRING_SERVICE, INSTAGRAM_USERNAME_KEY, username)
        keyring.set_password(KEYRING_SERVICE, username, password)
        logger.info("Instagram credentials stored securely in system keyring")
        return True
    except Exception as e:
        logger.error(f"Failed to store Instagram credentials in keyring: {str(e)}")
        return False

def setup_credentials_interactively() -> bool:
    """
    Interactive setup of all credentials
    
    Returns:
        bool: True if all credentials were successfully set up
    """
    print("Setting up PolitoMensa credentials")
    print("=================================")
    
    telegram_success = set_telegram_token()
    if not telegram_success:
        print("Warning: Failed to store Telegram token securely")
    
    instagram_success = set_instagram_credentials()
    if not instagram_success:
        print("Warning: Failed to store Instagram credentials securely")
    
    return telegram_success and instagram_success

if __name__ == "__main__":
    # Run interactive credential setup if this file is executed directly
    setup_credentials_interactively()
    print("\nYou can now run the bot!")
