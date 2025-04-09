from typing import Dict
import asyncio
import schedule
import time
import threading
import signal
import sys
import os
from src.logger import setup_logger, get_logger

class App:
    def __init__(self):
        # Set up logging first
        self.logger = setup_logger()
        self.logger.info("Initializing PolitoMensa application")
        
        from src.instapi import InstApi
        from src.telebot import Telebot
        
        # Store menus by cafeteria name and meal type
        self.menus: Dict[str, Dict[str, str]] = {}  # Format: {cafeteria: {"pranzo": menu1, "cena": menu2}}
        
        # Initialize components
        self.logger.debug("Initializing Instagram API client")
        self.instagram = InstApi(self)
        
        self.logger.debug("Initializing Telegram bot")
        self.telegram_bot = Telebot(self)
        
        # Set up daily menu fetch
        self.logger.debug("Setting up scheduler")
        self._setup_scheduler()
        
        # Initialize console commands (but don't start yet)
        self.logger.debug("Initializing console commands")
        from src.console import ConsoleCommands
        self.console = ConsoleCommands(self)
    
    def _setup_scheduler(self):
        """Set up a scheduler to fetch menus daily"""
        schedule.every().day.at("07:00").do(self.scheduled_menu_fetch)
        self.logger.info("Scheduled daily menu fetch at 07:00")
        
        # Start scheduler in a separate thread
        scheduler_thread = threading.Thread(target=self._run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        self.logger.debug("Scheduler thread started")
    
    def _run_scheduler(self):
        """Run the scheduler loop with respect to the enabled/disabled state"""
        self.logger.debug("Scheduler loop started")
        while True:
            # Only run pending jobs if updates are enabled
            if hasattr(self, 'update_enabled') and self.update_enabled.is_set():
                schedule.run_pending()
            time.sleep(60)
    
    def scheduled_menu_fetch(self):
        """Fetches menus only if updates are enabled"""
        if hasattr(self, 'update_enabled') and self.update_enabled.is_set():
            self.logger.info("Running scheduled menu fetch (updates enabled)")
            return self.fetch_daily_menus()
        else:
            self.logger.info("Skipping scheduled menu fetch (updates disabled)")
            return None
    
    def fetch_daily_menus(self):
        """Fetch menus from Instagram with improved error handling"""
        self.logger.info("Fetching daily menus from Instagram")
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                self.menus = self.instagram.fetch_menus()
                menu_count = sum(1 for cafe in self.menus.values() for meal in cafe.values() 
                               if meal and not any(err in meal for err in ["not available", "Error"]))
                
                if menu_count > 0:
                    self.logger.info(f"Daily menus updated successfully: {menu_count} menus for {len(self.menus)} cafeterias")
                    return self.menus
                else:
                    # If we got no valid menus, retry
                    retry_count += 1
                    self.logger.warning(f"No valid menus found (attempt {retry_count}/{max_retries})")
                    if retry_count < max_retries:
                        time.sleep(5)  # Wait before retrying
                    
            except Exception as e:
                retry_count += 1
                self.logger.error(f"Error fetching daily menus (attempt {retry_count}/{max_retries}): {str(e)}", 
                                 exc_info=True)
                if retry_count < max_retries:
                    time.sleep(5)  # Wait before retrying
        
        # If we get here, all retries failed
        self.logger.error(f"Failed to fetch menus after {max_retries} attempts")
        
        # Fall back to empty or existing menus
        if not self.menus:
            self.logger.warning("Falling back to placeholder menus")
            self.menus = {}
            for cafeteria in self.instagram.cafeterias:
                self.menus[cafeteria] = {
                    "pranzo": self.instagram._generate_placeholder_menu(cafeteria, "pranzo"),
                    "cena": self.instagram._generate_placeholder_menu(cafeteria, "cena")
                }
        
        return self.menus
    
    def get_menu(self, cafeteria_name: str, meal_type: str = "pranzo") -> str:
        """Get menu for a specific cafeteria and meal type"""
        self.logger.debug(f"Getting {meal_type} menu for cafeteria: {cafeteria_name}")
        if not self.menus:
            self.logger.info("Menus not available, fetching now")
            # If menus are empty, fetch them first
            self.fetch_daily_menus()
        
        # Get cafeteria's menus
        cafeteria_menus = self.menus.get(cafeteria_name, {})
        
        # Get specific meal type menu
        menu = cafeteria_menus.get(meal_type, "Menu not available for this cafeteria/meal")
        
        if menu == "Menu not available for this cafeteria/meal":
            self.logger.warning(f"{meal_type.capitalize()} menu not found for cafeteria: {cafeteria_name}")
        
        return menu
    
    def run(self, debug=False, enable_console=True, demo_mode=False):
        """Start the application with better error handling and recovery"""
        self.logger.info(f"Starting application with debug={debug}, console={enable_console}, demo={demo_mode}")
        
        # Check if we're running in dual terminal mode and mark the process
        if os.environ.get("POLITOMENSA_LOG_TERMINAL") != "1" and not os.environ.get("POLITOMENSA_SINGLE_TERMINAL"):
            os.environ["POLITOMENSA_MAIN_TERMINAL"] = "1"
            self.logger.debug("Running in main terminal of dual terminal mode")

        # Store demo mode setting for other components
        self.demo_mode = demo_mode
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            self.logger.info(f"Received signal {sig}, shutting down gracefully")
            if hasattr(self, 'console') and self.console:
                self.console.stop()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Only start console in command terminal, not log terminal
        if enable_console and os.environ.get("POLITOMENSA_LOG_TERMINAL") != "1":
            self.console.start(show_welcome=True)
            self.logger.info("Console started and ready for commands")
            # Set up the update control event early
            self.update_enabled = threading.Event()
            self.update_enabled.set()  # Enable updates by default
        
        # If console is not enabled, still create the update control event
        if not hasattr(self, 'update_enabled'):
            self.update_enabled = threading.Event()
            self.update_enabled.set()
        
        # Login to Instagram (unless in demo mode)
        if not demo_mode:
            self.logger.info("Logging in to Instagram")
            login_success = self.instagram.login()
            if not login_success:
                self.logger.error("Failed to login to Instagram")
                self.logger.info("Continuing in limited mode with placeholder menus")
        else:
            self.logger.info("Running in demo mode - using placeholder menus")
            self.instagram.demo_mode = True
        
        # Initial menu fetch
        self.logger.info("Performing initial menu fetch")
        self.fetch_daily_menus()
        
        # Start Telegram bot 
        self.logger.info("Starting Telegram bot")
        
        # Start the bot in a separate thread so we can continue execution
        def start_bot():
            self.telegram_bot.run(debug)
        
        bot_thread = threading.Thread(target=start_bot)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Wait a moment for the bot to initialize
        time.sleep(3)
        
        # Now signal console to allow command prompt to appear
        if enable_console:
            self.console.signal_ready()  # Signal console to start showing prompts
            
        # Keep the main thread alive while the bot is running
        try:
            while bot_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Application stopped by user")

    def run_console_only(self):
        """Start only the console interface without other components"""
        self.logger.info("Starting in console-only mode")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            self.logger.info(f"Received signal {sig}, shutting down gracefully")
            if hasattr(self, 'console') and self.console:
                self.console.stop()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start console commands
        self.console.start(show_welcome=True)
        self.logger.info("Console started in standalone mode")
        
        # Setup update control event
        self.update_enabled = threading.Event()
        self.update_enabled.set()  # Enable updates by default
        
        # Signal console ready
        self.console.signal_ready()
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Console-only mode stopped by user")