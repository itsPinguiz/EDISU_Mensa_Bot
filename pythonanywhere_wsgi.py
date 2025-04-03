import os
import sys

# Add your project directory to the sys.path
path = '/home/yourusername/PolitoMensa'
if path not in sys.path:
    sys.path.append(path)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# Import your app and set up logging
from src.logger import setup_logger
logger = setup_logger()
logger.info("Starting PolitoMensa Bot on PythonAnywhere")

# Import and start your app
from src.app import App
app = App()

# Don't call app.run() here - we'll use scheduled tasks instead
# Instead, just ensure the application is initialized
logger.info("PolitoMensa Bot initialized and ready")

# For web app - simple ping endpoint
def application(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [b'PolitoMensa Bot is running']
