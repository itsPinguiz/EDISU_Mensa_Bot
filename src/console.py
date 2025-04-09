import threading
import logging
import os
import sys
import time
import asyncio
import platform
from typing import Dict, Callable, List
from src.logger import get_logger
import cmd
from colorama import init, Fore, Back, Style, AnsiToWin32

# Initialize colorama correctly - autoreset must be False for fine-grained control
init(autoreset=False, convert=True, strip=False, wrap=True)

# Ensure ANSI colors work in Windows command prompt/terminal
if platform.system() == "Windows":
    import ctypes
    try:
        # Enable VT100 terminal processing (ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004)
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(handle, mode)
    except Exception as e:
        print(f"Warning: Could not enable VT processing: {e}")
    
    # Force colors to work with the "color" command in cmd
    os.system("")

class ConsoleCommands(cmd.Cmd):
    """
    Simple console command system for PolitoMensa using standard input/output.
    Streamlined version that only handles commands - logs go to separate terminal.
    """
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.logger = get_logger()
        self.running = False
        self.command_thread = None
        self.ready_event = threading.Event()
        
        # Command history
        self.command_history = []
        
        # Dictionary mapping command names to their handler functions
        self.commands: Dict[str, Callable] = {
            'help': self.cmd_help,
            'status': self.cmd_status,
            'update': self.cmd_update,
            'log': self.cmd_log,
            'cafeterias': self.cmd_cafeterias,
            'menu': self.cmd_show_menu,
            'notify': self.cmd_notify,
            'restart': self.cmd_restart,
            'quit': self.cmd_quit,
            'exit': self.cmd_quit,
            'start-updates': self.cmd_start_updates,
            'stop-updates': self.cmd_stop_updates,
        }
        
        self.logger.info("Simple console command system initialized")
        self.prompt = f"{Fore.GREEN}mensa>{Style.RESET_ALL} "
        self.intro = None  # Will be set when showing welcome
        
        # Apply Windows-specific console enhancements
        if platform.system() == "Windows":
            # Ensure stdout is properly wrapped
            sys.stdout = AnsiToWin32(sys.stdout).stream
            
            # Enable virtual terminal processing for colors in Windows terminal
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except:
                self.logger.warning("Could not enable virtual terminal processing")
    
    def start(self, show_welcome=True):
        """Start the console command system"""
        if self.running:
            self.logger.warning("Console commands already running")
            return
        
        self.running = True
        self.ready_event.clear()
        
        # Show welcome message
        if show_welcome:
            self._print_header()
            print("Type 'help' for available commands")
        
        # Start the console thread
        self.command_thread = threading.Thread(target=self._console_thread)
        self.command_thread.daemon = True
        self.command_thread.start()
        
        # Signal that we're ready for commands
        self.ready_event.set()
    
    def _console_thread(self):
        """Main console thread that accepts and processes commands"""
        try:
            self.ready_event.wait()  # Wait until application signals we can show the prompt
            
            # Make sure stdout is not redirected 
            if hasattr(sys.stdout, 'name') and sys.stdout.name == os.devnull:
                sys.stdout = sys.__stdout__
                # Re-initialize colorama after restoring stdout
                init(autoreset=False, convert=True, strip=False, wrap=True)
                self.logger.debug("Restored stdout for console commands")
            
            # Ensure ANSI colors are enabled
            if platform.system() == "Windows":
                os.system("")  # This magic command enables ANSI colors in Windows terminal
                
            # Show header at startup
            self._print_header()
                
            while self.running:
                try:
                    # Explicitly print prompt with proper styling
                    sys.stdout.write(f"{Fore.GREEN}mensa>{Style.RESET_ALL} ")
                    sys.stdout.flush()
                    
                    # Get input directly
                    command = input().strip()
                    
                    if not command:
                        continue
                    
                    # Process the command
                    self._process_command(command)
                    
                except EOFError:
                    # Ctrl+D pressed
                    print("\nUse 'quit' or 'exit' to exit.")
                except KeyboardInterrupt:
                    # Ctrl+C pressed
                    print("\nInterrupted. Use 'quit' or 'exit' to exit.")
                except Exception as e:
                    self.logger.error(f"Error in console thread: {str(e)}", exc_info=True)
                    print(f"Error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in console main loop: {str(e)}", exc_info=True)
    
    def _process_command(self, command_text):
        """Process a command entered by the user"""
        if not command_text:
            return
            
        # Add to history
        self.command_history.append(command_text)
        if len(self.command_history) > 50:
            self.command_history = self.command_history[-50:]
        
        # Parse command
        parts = command_text.split()
        if not parts:
            return
            
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        try:
            # Execute the command if it exists
            if cmd in self.commands:
                try:
                    # Execute command
                    self.commands[cmd](args)
                except Exception as e:
                    print(f"Error executing command '{cmd}': {str(e)}")
                    self.logger.error(f"Error executing command '{cmd}': {str(e)}", exc_info=True)
            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands")
        except Exception as e:
            self.logger.error(f"Unexpected error processing command: {str(e)}", exc_info=True)
            print(f"Error: {str(e)}")
    
    def signal_ready(self):
        """Signal that the console should start showing prompts"""
        self.ready_event.set()
    
    def stop(self):
        """Stop the console command system"""
        self.running = False
        if self.command_thread and self.command_thread.is_alive():
            self.logger.info("Stopping console command system")
    
    def cmd_help(self, args: List[str]) -> None:
        """Display help information about available commands"""
        print("\n=== Available Commands ===")
        print("help          - Show this help message")
        print("status        - Show application status")
        print("update        - Force update of menus")
        print("start-updates - Enable scheduled menu updates")
        print("stop-updates  - Disable scheduled menu updates")
        print("log LEVEL     - Change logging level (DEBUG, INFO, WARNING, ERROR)")
        print("cafeterias    - List available cafeterias")
        print("menu CAFE     - Show menu for a cafeteria")
        print("notify MSG    - Send notification to all active chats")
        print("restart       - Restart the Telegram bot")
        print("quit/exit     - Exit the application")
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
        
        # Get active chats information
        active_chats_count = 0
        if hasattr(self.app, 'telegram_bot') and hasattr(self.app.telegram_bot, 'active_chats'):
            active_chats_count = len(self.app.telegram_bot.active_chats)
        
        print("\n=== Application Status ===")
        print(f"Instagram: {instagram_status}")
        print(f"Telegram: {telegram_status}")
        print(f"Active Telegram chats: {active_chats_count}")
        print(f"Cafeterias: {num_cafeterias}")
        print(f"Active menus: {num_menus}")
        
        # Show current logging level
        current_level = logging.getLevelName(self.logger.level)
        print(f"Logging level: {current_level}")
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
            print("Current log level: " + logging.getLevelName(self.logger.level))
            print("Usage: log LEVEL")
            print("Example: log DEBUG")
            print("Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL")
            return
        
        level_name = args[0].upper()
        
        try:
            # Get the numeric level from the name
            level = getattr(logging, level_name)
            
            # Set the level for the logger
            self.logger.setLevel(level)
            print(f"✅ Logging level set to {level_name}")
            
            # Also set environment variable for future runs
            os.environ["POLITOMENSA_LOG_LEVEL"] = level_name
            print(f"✅ POLITOMENSA_LOG_LEVEL environment variable set to {level_name}")
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
    
    def cmd_notify(self, args: List[str]) -> None:
        """Send a notification to all active chats"""
        if not args:
            print("Usage: notify MESSAGE")
            print("Example: notify The bot will be down for maintenance from 22:00 to 23:00")
            return
        
        # Combine all arguments into a single message
        message = " ".join(args)
        
        print(f"⚠️ You are about to send the following message to all active chats:")
        print(f"\n\"{message}\"\n")
        
        confirmation = input("Are you sure you want to send this message? (y/n): ").lower()
        
        if confirmation != 'y' and confirmation != 'yes':
            print("Message sending cancelled.")
            return
        
        try:
            # Ask the Telegram bot to send the notification
            num_sent = self.app.telegram_bot.send_notification(message)
            if num_sent > 0:
                print(f"✅ Message sent to {num_sent} active chats")
            else:
                print("⚠️ No active chats found. Message was not sent.")
        except Exception as e:
            print(f"❌ Error sending notification: {str(e)}")
    
    def cmd_restart(self, args: List[str]) -> None:
        """Restart the Telegram bot"""
        print("Restarting Telegram bot...")
        
        confirmation = input("Are you sure you want to restart the bot? Active users will be disconnected. (y/n): ").lower()
        
        if confirmation != 'y' and confirmation != 'yes':
            print("Restart cancelled.")
            return
        
        try:
            # First notify users of restart
            try:
                self.app.telegram_bot.send_notification("Bot is restarting. Please wait a moment...")
            except Exception as e:
                self.logger.warning(f"Failed to send restart notification: {str(e)}")
            
            # Start restart in a separate thread to avoid blocking
            threading.Thread(target=self._perform_restart, daemon=True).start()
            print("✅ Restart initiated. Bot will restart momentarily...")
            
        except Exception as e:
            print(f"❌ Error initiating restart: {str(e)}")
            self.logger.error(f"Error during restart: {str(e)}", exc_info=True)

    def _perform_restart(self):
        """Execute the actual restart process in a separate thread"""
        try:
            # Create a new instance of the Telegram bot
            import importlib
            from src.telebot import Telebot
            
            # Give users a chance to see the notification
            time.sleep(2)
            
            # Log restart attempt
            self.logger.info("Performing Telegram bot restart")
            
            # Keep a reference to the old bot
            old_bot = self.app.telegram_bot
            old_active_chats = old_bot.active_chats.copy()  # Make a copy to preserve active chats
            old_debug_mode = old_bot.debug_mode  # Preserve debug mode
            
            # First, stop the old bot's updater
            # Create a temporary event loop to shut down the old bot properly
            shutdown_loop = asyncio.new_event_loop()
            
            async def shutdown_old_bot():
                try:
                    # Try to stop the updater if it's running
                    if hasattr(old_bot.application, 'updater') and old_bot.application.updater.running:
                        await old_bot.application.updater.stop()
                    # Stop the application if it's running
                    if hasattr(old_bot.application, 'running') and old_bot.application.running:
                        await old_bot.application.stop()
                    # Complete shutdown
                    await old_bot.application.shutdown()
                    self.logger.info("Successfully stopped old bot instance")
                except Exception as e:
                    self.logger.error(f"Error stopping old bot: {str(e)}")
            
            try:
                # Run the shutdown in the temporary loop
                shutdown_loop.run_until_complete(shutdown_old_bot())
            finally:
                shutdown_loop.close()
            
            # Wait a moment to ensure resources are freed
            time.sleep(3)
            
            # Create and start a new bot
            self.app.telegram_bot = Telebot(self.app)
            self.app.telegram_bot.active_chats = old_active_chats  # Restore active chats
            self.app.telegram_bot.debug_mode = old_debug_mode  # Restore debug mode
            
            # Start the new bot in a non-blocking way
            threading.Thread(target=lambda: self.app.telegram_bot.run(old_debug_mode), daemon=True).start()
            
            # Wait for bot to initialize
            time.sleep(5)
            
            # Notify users of successful restart
            try:
                self.app.telegram_bot.send_notification("Bot has been restarted successfully")
                self.logger.info("Telegram bot restarted successfully")
            except Exception as e:
                self.logger.error(f"Failed to send restart completion notification: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Failed to restart Telegram bot: {str(e)}", exc_info=True)
            print(f"❌ Bot restart failed: {str(e)}")
    
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
    
    def cmd_start_updates(self, args: List[str]) -> None:
        """Start menu updates (enable scheduler)"""
        if hasattr(self.app, 'update_enabled'):
            if self.app.update_enabled.is_set():
                print("✅ Menu updates are already enabled")
            else:
                self.app.update_enabled.set()
                print("✅ Menu updates have been enabled")
                self.logger.info("Menu updates enabled via console command")
        else:
            print("❌ Update control not available")
        
    def cmd_stop_updates(self, args: List[str]) -> None:
        """Stop menu updates (disable scheduler)"""
        if hasattr(self.app, 'update_enabled'):
            if not self.app.update_enabled.is_set():
                print("ℹ️ Menu updates are already disabled")
            else:
                self.app.update_enabled.clear()
                print("✅ Menu updates have been disabled")
                self.logger.info("Menu updates disabled via console command")
        else:
            print("❌ Update control not available")

    def _print_header(self):
        """Print a styled header"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Use explicit writes with flush to ensure proper display
        sys.stdout.write(f"{Fore.CYAN}╔════════════════════════════════════════╗\n")
        sys.stdout.write(f"{Fore.CYAN}║  {Fore.WHITE}{Style.BRIGHT}PolitoMensa Console Interface v1.0{Style.NORMAL}{Fore.CYAN}    ║\n")
        sys.stdout.write(f"{Fore.CYAN}╚════════════════════════════════════════╝{Style.RESET_ALL}\n")
        sys.stdout.flush()

    def _print_status(self, status: str, color: str = Fore.WHITE):
        """Print a status message with color"""
        print(f"{color}[*] {status}{Style.RESET_ALL}", flush=True)

    def _print_error(self, error: str):
        """Print an error message"""
        print(f"{Fore.RED}[!] Error: {error}{Style.RESET_ALL}", flush=True)

    def _print_success(self, message: str):
        """Print a success message"""
        print(f"{Fore.GREEN}[+] {message}{Style.RESET_ALL}", flush=True)

    def signal_ready(self):
        """Signal that the application is ready for commands"""
        self.ready_event.set()

    def preloop(self):
        """Setup before starting the command loop"""
        if self.intro:
            self._print_header()
            # Print intro line by line with explicit resets
            for line in self.intro.split('\n'):
                if line:
                    print(line, flush=True)
        self.ready_event.wait()

    def emptyline(self):
        """Do nothing on empty line"""
        pass

    def do_status(self, arg):
        """Show current bot status"""
        if not hasattr(self.app, 'update_enabled'):
            self._print_error("Update status not available")
            return

        status = "ENABLED" if self.app.update_enabled.is_set() else "DISABLED"
        status_color = Fore.GREEN if status == "ENABLED" else Fore.RED
        
        print(f"\n{Fore.CYAN}╔══════════════════════════════╗")
        print(f"{Fore.CYAN}║       System Status          ║")
        print(f"{Fore.CYAN}╠══════════════════════════════╣")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Updates: {status_color}{status:<14}{Style.RESET_ALL}{Fore.CYAN} ║")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Demo Mode: {Fore.YELLOW}{str(self.app.demo_mode):<13}{Style.RESET_ALL}{Fore.CYAN} ║")
        print(f"{Fore.CYAN}╚══════════════════════════════╝{Style.RESET_ALL}\n")

    def do_enable(self, arg):
        """Enable menu updates"""
        if hasattr(self.app, 'update_enabled'):
            self.app.update_enabled.set()
            self._print_success("Menu updates enabled")
        else:
            self._print_error("Update control not available")

    def do_disable(self, arg):
        """Disable menu updates"""
        if hasattr(self.app, 'update_enabled'):
            self.app.update_enabled.clear()
            self._print_success("Menu updates disabled")
        else:
            self._print_error("Update control not available")

    def do_fetch(self, arg):
        """Force fetch menus now"""
        try:
            self._print_status("Fetching menus...", Fore.CYAN)
            menus = self.app.fetch_daily_menus()
            if menus:
                self._print_success(f"Successfully fetched menus for {len(menus)} cafeterias")
                for cafeteria in menus:
                    print(f"{Fore.CYAN}  • {cafeteria}{Style.RESET_ALL}", flush=True)
            else:
                self._print_error("No menus were fetched")
        except Exception as e:
            self._print_error(f"Failed to fetch menus: {str(e)}")

    def do_show(self, arg):
        """Show menu for a specific cafeteria: show <cafeteria_name> [pranzo|cena]"""
        args = arg.split()
        if not args:
            self._print_error("Please specify a cafeteria name")
            return

        cafeteria = args[0]
        meal_type = args[1] if len(args) > 1 else "pranzo"

        try:
            menu = self.app.get_menu(cafeteria, meal_type)
            print(f"\n{Fore.CYAN}=== Menu for {cafeteria} ({meal_type}) ==={Style.RESET_ALL}")
            print(f"{Fore.WHITE}{menu}{Style.RESET_ALL}", flush=True)
        except Exception as e:
            self._print_error(f"Failed to get menu: {str(e)}")

    def do_list(self, arg):
        """List all available cafeterias"""
        print(f"\n{Fore.CYAN}╔═══════════════════════════════════════╗")
        print(f"{Fore.CYAN}║         Available Cafeterias           ║")
        print(f"{Fore.CYAN}╠═══════════════════════════════════════╣{Style.RESET_ALL}")
        
        for i, cafe in enumerate(self.app.instagram.cafeterias, 1):
            print(f"{Fore.CYAN}║{Style.RESET_ALL}  {Fore.YELLOW}{i}.{Style.RESET_ALL} {Fore.WHITE}{cafe:<30}{Fore.CYAN}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╚═══════════════════════════════════════╝{Style.RESET_ALL}\n")

    def do_exit(self, arg):
        """Exit the console"""
        self._print_status("Shutting down...", Fore.YELLOW)
        self.running = False
        return True

    def do_clear(self, arg):
        """Clear the console screen"""
        self._print_header()
        return False

    def default(self, line):
        """Handle unknown commands"""
        self._print_error(f"Unknown command: {line}")
        print(f"Type {Fore.CYAN}help{Style.RESET_ALL} for a list of commands", flush=True)

    def do_help(self, arg):
        """Show help information with styled output"""
        self._print_header()
        
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════╗")
        print(f"{Fore.CYAN}║          Available Commands               ║")
        print(f"{Fore.CYAN}╠══════════════════════════════════════════╣{Style.RESET_ALL}")
        
        commands = [
            ("help", "Show this help message"),
            ("status", "Show application status"),
            ("update", "Force update of menus"),
            ("start-updates", "Enable scheduled menu updates"),
            ("stop-updates", "Disable scheduled menu updates"),
            ("log LEVEL", "Change logging level (DEBUG, INFO, WARNING, ERROR)"),
            ("cafeterias", "List available cafeterias"),
            ("menu CAFE", "Show menu for a cafeteria"),
            ("notify MSG", "Send notification to all active chats"),
            ("restart", "Restart the Telegram bot"),
            ("quit/exit", "Exit the application")
        ]
        
        # Calculate padding for alignment
        max_cmd_length = max(len(cmd[0]) for cmd in commands)
        
        for cmd, desc in commands:
            print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.YELLOW}{cmd:<{max_cmd_length}}{Style.RESET_ALL} - {Fore.WHITE}{desc}{' ' * (37-len(desc))}{Fore.CYAN}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╚══════════════════════════════════════════╝{Style.RESET_ALL}")
        print()

    def do_status(self, arg):
        """Show application status with styled output"""
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════╗")
        print(f"{Fore.CYAN}║            System Status                 ║")
        print(f"{Fore.CYAN}╠══════════════════════════════════════════╣{Style.RESET_ALL}")
        
        # Instagram Status
        insta_status = "Logged in" if self.app.instagram.logged_in else "Not logged in"
        insta_color = Fore.GREEN if self.app.instagram.logged_in else Fore.RED
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Instagram: {insta_color}{insta_status:<27}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Telegram Status
        telegram_status = "Running" if hasattr(self.app.telegram_bot, 'application') else "Not running"
        telegram_color = Fore.GREEN if telegram_status == "Running" else Fore.RED
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Telegram: {telegram_color}{telegram_status:<28}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Active chats
        chat_count = len(self.app.telegram_bot.active_chats) if hasattr(self.app.telegram_bot, 'active_chats') else 0
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Active chats: {Fore.YELLOW}{chat_count:<25}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Cafeteria count
        cafe_count = len(self.app.instagram.cafeterias)
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Cafeterias: {Fore.YELLOW}{cafe_count:<27}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Menu count
        menu_count = sum(1 for cafe in self.app.menus.values() for meal in cafe.values() if meal)
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Active menus: {Fore.YELLOW}{menu_count:<25}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Logging level
        log_level = logging.getLogger().getEffectiveLevel()
        level_name = logging.getLevelName(log_level)
        level_color = {
            'DEBUG': Fore.MAGENTA,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED
        }.get(level_name, Fore.WHITE)
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Log level: {level_color}{level_name:<27}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Updates status
        updates_status = "Enabled" if self.app.update_enabled.is_set() else "Disabled"
        updates_color = Fore.GREEN if updates_status == "Enabled" else Fore.RED
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Updates: {updates_color}{updates_status:<29}{Fore.CYAN}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╚══════════════════════════════════════════╝{Style.RESET_ALL}")
        print()

    def emptyline(self):
        """Handle empty line input"""
        self._print_status("Type a command or 'help' for available commands", Fore.CYAN)

    # Command shortcuts
    do_quit = do_exit
    do_EOF = do_exit

