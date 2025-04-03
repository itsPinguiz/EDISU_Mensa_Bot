from typing import Dict
import asyncio
import schedule
import time
import threading
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
    
    def _setup_scheduler(self):
        """Set up a scheduler to fetch menus daily"""
        schedule.every().day.at("07:00").do(self.fetch_daily_menus)
        self.logger.info("Scheduled daily menu fetch at 07:00")
        
        # Start scheduler in a separate thread
        scheduler_thread = threading.Thread(target=self._run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        self.logger.debug("Scheduler thread started")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        self.logger.debug("Scheduler loop started")
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def fetch_daily_menus(self):
        """Fetch menus from Instagram"""
        self.logger.info("Fetching daily menus from Instagram")
        try:
            self.menus = self.instagram.fetch_menus()
            self.logger.info(f"Daily menus updated successfully for {len(self.menus)} cafeterias")
            return self.menus
        except Exception as e:
            self.logger.error(f"Error fetching daily menus: {str(e)}", exc_info=True)
            return {}
    
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
    
    def run(self, debug=False):
        """Start the telegram bot"""
        self.logger.info(f"Starting application with debug={debug}")
        
        # Login to Instagram
        self.logger.info("Logging in to Instagram")
        login_success = self.instagram.login()
        if not login_success:
            self.logger.error("Failed to login to Instagram")
        
        # Initial menu fetch
        self.logger.info("Performing initial menu fetch")
        self.fetch_daily_menus()
        
        # Run the bot
        self.logger.info("Starting Telegram bot")
        self.telegram_bot.run(debug)

#main 
if __name__ == "__main__":
    from src.app import App
    from src.instapi import InstApi  
    from src.telebot import Telebot

    app = App()

    app.run(debug=True)