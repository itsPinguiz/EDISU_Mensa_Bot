import threading
import logging
import os
import sys
import platform
# Conditionally import readline (not available on Windows)
if platform.system() != 'Windows':
    try:
        import readline  # For better command line editing support
    except ImportError:
        pass  # readline not available, history and editing features will be limited
from typing import Dict, Callable, List, Any, Optional
import time
from src.logger import get_logger

class ConsoleCommands:
    """
    Console command system for PolitoMensa that allows interaction while running
    """
    def __init__(self, app):
        self.app = app
        self.logger = get_logger()
        self.running = False
        self.command_thread = None
        self.ready_event = threading.Event()  # Add event for synchronization
        
        # Dictionary mapping command names to their handler functions
        self.commands: Dict[str, Callable] = {
            'help': self.cmd_help,
            'status': self.cmd_status,
            'update': self.cmd_update,
            'log': self.cmd_log,
            'cafeterias': self.cmd_cafeterias,
            'menu': self.cmd_show_menu,
            'quit': self.cmd_quit,
            'exit': self.cmd_quit,
        }
        
        self.logger.info("Console command system initialized")
    
    def start(self, show_welcome=True):
        """Start the console command input loop in a separate thread"""
        if self.running:
            self.logger.warning("Console commands already running")
            return
        
        self.running = True
        self.ready_event.clear()  # Ensure event starts in unset state
        self.command_thread = threading.Thread(target=self._command_loop)
        self.command_thread.daemon = True  # Thread will exit when main program exits
        self.command_thread.start()
        self.logger.info("Console command system started")
        
        # Show initial help message only if requested
        if show_welcome:
            self.show_welcome()
            self.ready_event.set()  # Allow command loop to proceed

    def signal_ready(self):
        """Signal that the console should start showing prompts"""
        self.ready_event.set()

    def show_welcome(self):
        """Display the welcome message"""
        print("\n=== EDISU Mensa Bot Console Commands ===")
        print("Type 'help' for available commands")
        print("==========================================\n")
    
    def stop(self):
        """Stop the console command input loop"""
        self.running = False
        if self.command_thread and self.command_thread.is_alive():
            self.logger.info("Stopping console command system")
            # The thread should terminate on its own since self.running is False
            
    def _command_loop(self):
        """Main loop that receives and processes commands"""
        # Wait for the ready signal before showing any prompt
        self.ready_event.wait()
        
        while self.running:
            try:
                # Print a prompt and get input
                # Using end='' and flush=True to keep the cursor on the same line
                print("> ", end='', flush=True)
                command = input().strip()
                
                if not command:
                    continue
                
                # Parse the command and arguments
                parts = command.split()
                cmd = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                # Execute the command if it exists
                if cmd in self.commands:
                    try:
                        self.commands[cmd](args)
                    except Exception as e:
                        print(f"Error executing command '{cmd}': {str(e)}")
                        self.logger.error(f"Error executing command '{cmd}': {str(e)}", exc_info=True)
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")
            
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                print("\nUse 'quit' or 'exit' to exit the application")
            except EOFError:
                # Handle Ctrl+D (EOF)
                print("\nUse 'quit' or 'exit' to exit the application")
            except Exception as e:
                print(f"Error in command loop: {str(e)}")
                self.logger.error(f"Error in command loop: {str(e)}", exc_info=True)
    
    # Command handlers
    def cmd_help(self, args: List[str]) -> None:
        """Display help information about available commands"""
        print("\n=== Available Commands ===")
        print("help       - Show this help message")
        print("status     - Show application status")
        print("update     - Force update of menus")
        print("log LEVEL  - Change logging level (DEBUG, INFO, WARNING, ERROR)")
        print("cafeterias - List available cafeterias")
        print("menu CAFE  - Show menu for a cafeteria")
        print("quit/exit  - Exit the application")
        print("========================\n")
    
    def cmd_status(self, args: List[str]) -> None:
        """Show the current status of the application"""
        instagram_status = "Logged in" if self.app.instagram.logged_in else "Not logged in"
        telegram_status = "Running" if hasattr(self.app, 'telegram_bot') else "Not running"
        
        # Get the number of cafeterias and menus
        num_cafeterias = len(self.app.instagram.cafeterias)
        num_menus = sum(1 for cafeteria in self.app.menus.values() 
                      for meal_type in cafeteria.values() 
                      if meal_type and "not available" not in meal_type)
        
        print("\n=== Application Status ===")
        print(f"Instagram: {instagram_status}")
        print(f"Telegram: {telegram_status}")
        print(f"Cafeterias: {num_cafeterias}")
        print(f"Active menus: {num_menus}")
        
        # Show current logging level
        current_level = logging.getLevelName(self.logger.level)
        console_level = logging.getLevelName(self.logger.handlers[0].level)
        file_level = logging.getLevelName(self.logger.handlers[1].level) if len(self.logger.handlers) > 1 else "N/A"
        
        print(f"Logging level: {current_level} (Console: {console_level}, File: {file_level})")
        print("=========================\n")
    
    def cmd_update(self, args: List[str]) -> None:
        """Force an update of the menus"""
        print("Updating menus... This may take a moment.")
        
        try:
            start_time = time.time()
            menus = self.app.fetch_daily_menus()
            elapsed_time = time.time() - start_time
            
            if menus:
                num_menus = sum(1 for cafeteria in menus.values() 
                              for meal_type in cafeteria.values() 
                              if meal_type and "not available" not in meal_type)
                print(f"✅ Menus updated successfully in {elapsed_time:.2f} seconds")
                print(f"   Retrieved {num_menus} menus for {len(menus)} cafeterias")
            else:
                print("❌ Menu update returned empty results")
        except Exception as e:
            print(f"❌ Error updating menus: {str(e)}")
    
    def cmd_log(self, args: List[str]) -> None:
        """Change the logging level"""
        if not args:
            print("Current log level: " + logging.getLevelName(self.logger.handlers[0].level))
            print("Usage: log LEVEL")
            print("Example: log DEBUG")
            print("Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL")
            return
        
        level_name = args[0].upper()
        
        try:
            # Get the numeric level from the name
            level = getattr(logging, level_name)
            
            # Set the level for the console handler (usually the first handler)
            if self.logger.handlers:
                self.logger.handlers[0].setLevel(level)
                print(f"✅ Console logging level set to {level_name}")
                
                # Also set environment variable for future runs
                os.environ["POLITOMENSA_LOG_LEVEL"] = level_name
                print(f"✅ POLITOMENSA_LOG_LEVEL environment variable set to {level_name}")
            else:
                print("❌ No handlers found for logger")
        except AttributeError:
            print(f"❌ Invalid log level: {level_name}")
            print("Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    
    def cmd_cafeterias(self, args: List[str]) -> None:
        """List all available cafeterias"""
        print("\n=== Available Cafeterias ===")
        for i, cafeteria in enumerate(self.app.instagram.cafeterias, 1):
            print(f"{i}. {cafeteria}")
        print("===========================\n")
    
    def cmd_show_menu(self, args: List[str]) -> None:
        """Show a menu for a cafeteria"""
        if not args:
            print("Usage: menu CAFETERIA [meal_type]")
            print("Example 1: menu \"Principe Amedeo\"")
            print("Example 2: menu Castelfidardo cena")
            print("\nAvailable cafeterias:")
            self.cmd_cafeterias([])
            return
        
        # Handle multi-word cafeteria names
        cafeteria_name = " ".join(args[0:-1] if len(args) > 1 and args[-1] in ["pranzo", "cena"] else args)
        meal_type = args[-1] if len(args) > 1 and args[-1] in ["pranzo", "cena"] else "pranzo"
        
        # Check if cafeteria exists
        valid_cafeterias = self.app.instagram.cafeterias
        if cafeteria_name not in valid_cafeterias:
            # Try to find a case-insensitive match
            matches = [c for c in valid_cafeterias if c.lower() == cafeteria_name.lower()]
            if matches:
                cafeteria_name = matches[0]  # Use the correctly cased name
            else:
                print(f"❌ Cafeteria '{cafeteria_name}' not found")
                print("Valid cafeterias:")
                self.cmd_cafeterias([])
                return
        
        # Get and display the menu
        try:
            menu = self.app.get_menu(cafeteria_name, meal_type)
            print(f"\n=== {cafeteria_name} - {meal_type.capitalize()} ===")
            print(menu)
            print("===========================\n")
        except Exception as e:
            print(f"❌ Error getting menu: {str(e)}")
    
    def cmd_quit(self, args: List[str]) -> None:
        """Exit the application"""
        print("Exiting application...")
        self.running = False
        # Use a delayed exit to allow this function to complete
        threading.Thread(target=self._delayed_exit).start()
    
    def _delayed_exit(self):
        """Exit the application after a short delay"""
        time.sleep(0.5)  # Short delay to let the command finish
        os._exit(0)  # Force exit
