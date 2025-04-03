#!/usr/bin/env python3
import os
import sys
from src.app import App
from src.logger import setup_logger

# Setup logger
logger = setup_logger()
logger.info("Starting PolitoMensa Bot through scheduled task")

# Initialize and run the app
app = App()
app.run(debug=False)

# The bot should keep running until the scheduled task is terminated
