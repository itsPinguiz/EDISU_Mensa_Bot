import threading
import logging
import os
import sys
import platform
import asyncio
import time
from typing import Dict, Callable, List, Any, Optional
import queue
from src.logger import get_logger

# Import curses with platform check
try:
    import curses
    from curses import textpad
    CURSES_AVAILABLE = True
except ImportError:
    CURSES_AVAILABLE = False
    print("Warning: curses module not available. Install with: pip install windows-curses")

class CursesLogHandler(logging.Handler):
    """Custom log handler that sends log messages to the curses interface"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        
    def emit(self, record):
        # Format the record and add to the queue for the UI thread to handle
        log_message = self.format(record)
        try:
            self.log_queue.put_nowait(log_message)
        except queue.Full:
            # If queue is full, remove oldest message and try again
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(log_message)
            except:
                pass  # If still can't add, just drop the message

class ConsoleCommands:
    """
    Console command system for PolitoMensa using curses for a more interactive UI
    """
    def __init__(self, app):
        self.app = app
        self.logger = get_logger()
        self.running = False
        self.command_thread = None
        self.ready_event = threading.Event()
        
        # Command history
        self.command_history = []
        self.history_index = 0
        
        # Queue for passing log messages to the UI thread
        self.log_queue = queue.Queue(maxsize=1000)
        
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
        }
        
        # Add our custom log handler
        self._setup_log_handler()
        
        self.logger.info("Console command system initialized")
    
    def _setup_log_handler(self):
        """Set up custom log handler to send logs to curses interface"""
        console_handler = CursesLogHandler(self.log_queue)
        # Set level to DEBUG to capture more logs in the UI
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(module)s:%(lineno)d] - %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        console_handler.setFormatter(formatter)
        
        # Add to root logger to catch all messages
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)
    
    def start(self, show_welcome=True):
        """Start the console command system in curses mode"""
        if self.running:
            self.logger.warning("Console commands already running")
            return
        
        if not CURSES_AVAILABLE:
            self.logger.warning("Curses not available - falling back to simple console mode")
            return self._start_simple_console()
        
        self.running = True
        self.ready_event.clear()
        
        # Show simple welcome message
        if show_welcome:
            print("\n=== EDISU Mensa Bot Console ===")
            print("Starting curses interface...")
            print("Press Ctrl+C to exit if the interface doesn't start properly")
            print("===============================\n")
            time.sleep(1)  # Short delay to allow seeing the message
        
        # Start the curses interface in the main thread
        self.command_thread = threading.Thread(target=self._curses_ui_thread)
        self.command_thread.daemon = True
        self.command_thread.start()
        
        # Signal we're ready
        self.ready_event.set()
    
    def _start_simple_console(self):
        """Fall back to simple console mode if curses is not available"""
        self.logger.warning("Using simple console interface (curses not available)")
        print("\n=== EDISU Mensa Bot Console Commands (Simple Mode) ===")
        print("Type 'help' for available commands")
        print("==================================================\n")
        
        # Simple console loop
        self.running = True
        self.ready_event.set()
        
        try:
            while self.running:
                try:
                    command = input("> ").strip()
                    if not command:
                        continue
                    
                    parts = command.split()
                    cmd = parts[0].lower()
                    args = parts[1:] if len(parts) > 1 else []
                    
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
                    print("\nUse 'quit' or 'exit' to exit the application")
                except EOFError:
                    print("\nUse 'quit' or 'exit' to exit the application")
        except Exception as e:
            print(f"Error in command loop: {str(e)}")
            self.logger.error(f"Error in simple console mode: {str(e)}", exc_info=True)
    
    def _curses_ui_thread(self):
        """Main curses UI thread"""
        try:
            # Initialize curses
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(1)  # Show cursor
            curses.noecho()  # Don't echo input
            curses.cbreak()  # React to keys without Enter
            stdscr.keypad(True)  # Enable special keys
            
            # Initialize color pairs
            curses.init_pair(1, curses.COLOR_WHITE, -1)    # Normal text
            curses.init_pair(2, curses.COLOR_GREEN, -1)    # Success
            curses.init_pair(3, curses.COLOR_RED, -1)      # Error
            curses.init_pair(4, curses.COLOR_YELLOW, -1)   # Warning
            curses.init_pair(5, curses.COLOR_BLUE, -1)     # Info
            
            # Get screen dimensions
            max_y, max_x = stdscr.getmaxyx()
            
            # Create windows
            # Log window (top part) - Increase log area by making input smaller
            log_height = max_y - 2  # Increased from max_y - 3
            log_win = curses.newwin(log_height, max_x, 0, 0)
            log_win.scrollok(True)
            log_win.idlok(True)
            
            # Title bar at top
            title_win = curses.newwin(1, max_x, 0, 0)
            title_win.bkgd(' ', curses.color_pair(5) | curses.A_BOLD)
            title_text = "EDISU Mensa Bot Console"
            title_win.addstr(0, (max_x - len(title_text)) // 2, title_text)
            title_win.refresh()
            
            # Command input window (bottom part) - smaller to give more space to logs
            input_win = curses.newwin(2, max_x, max_y - 2, 0)  # Changed from 3 to 2
            input_win.border()
            input_win.addstr(0, 2, " Command ")
            input_win.refresh()
            
            # Text box for input - adjust position due to smaller input area
            box_win = curses.newwin(1, max_x - 4, max_y - 1, 2)  # Changed position
            # Store a reference to the input window for other methods to use
            self._curses_input_window = box_win
            box_win.refresh()
            
            # List to store log messages for scrolling
            log_messages = []
            
            # Redraw the current view
            def redraw_log_window():
                log_win.clear()
                visible_lines = log_height - 1  # Reserve one line for the title
                
                # Add logging indicator in title bar to show activity
                log_count = len(log_messages)
                title_win.clear()
                title_win.bkgd(' ', curses.color_pair(5) | curses.A_BOLD)
                status_text = f"EDISU Mensa Bot Console - {log_count} log messages"
                title_win.addstr(0, (max_x - len(status_text)) // 2, status_text)
                title_win.refresh()
                
                # If no logs yet, show a helpful message
                if not log_messages:
                    log_win.addstr(2, 2, "Waiting for logs... Bot activity will appear here.", 
                                  curses.color_pair(4))
                    log_win.refresh()
                    return
                
                # Show more recent logs (scroll to bottom automatically)
                start_idx = max(0, len(log_messages) - visible_lines)
                for i, msg in enumerate(log_messages[start_idx:start_idx + visible_lines]):
                    try:
                        # Truncate long messages to fit window width
                        if len(msg) > max_x - 2:
                            msg = msg[:max_x - 5] + "..."
                            
                        # Colorize based on log level
                        color = curses.color_pair(1)  # Default: white
                        if "ERROR" in msg:
                            color = curses.color_pair(3)  # Red
                        elif "WARNING" in msg:
                            color = curses.color_pair(4)  # Yellow
                        elif "INFO" in msg:
                            color = curses.color_pair(5)  # Blue
                        elif "DEBUG" in msg:
                            color = curses.color_pair(5)  # Blue
                        
                        log_win.addstr(i + 1, 1, msg, color)  # +1 to leave space for title
                    except curses.error:
                        # Handle edge cases (like writing to bottom-right corner)
                        pass
                log_win.refresh()
            
            # First display
            redraw_log_window()
            
            # Create an instance of OutputCapture for reuse
            output_capture = self.OutputCapture(log_messages)
            
            # Command processing function for the textbox
            def process_command(text):
                text = text.strip()
                if not text:
                    return
                
                # Add to history
                self.command_history.append(text)
                if len(self.command_history) > 50:  # Limit history size
                    self.command_history = self.command_history[-50:]
                self.history_index = len(self.command_history)
                
                # Parse and execute command
                parts = text.split()
                cmd = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                # Capture command output
                old_stdout = sys.stdout
                # Use the pre-created instance of OutputCapture
                sys.stdout = output_capture
                
                try:
                    if cmd in self.commands:
                        try:
                            # Log the command
                            log_messages.append(f"> {text}")
                            self.commands[cmd](args)
                        except Exception as e:
                            log_messages.append(f"Error executing command '{cmd}': {str(e)}")
                            self.logger.error(f"Error executing command '{cmd}': {str(e)}", exc_info=True)
                    else:
                        log_messages.append(f"Unknown command: {cmd}")
                        log_messages.append("Type 'help' for available commands")
                finally:
                    # Restore stdout
                    sys.stdout = old_stdout
                    redraw_log_window()
            
            # Set up terminal resize handler
            def handle_resize():
                # Get new dimensions
                new_y, new_x = stdscr.getmaxyx()
                
                # Resize and reposition windows - adjust for new smaller input area
                log_win.resize(new_y - 2, new_x)  # Changed from new_y - 3
                title_win.resize(1, new_x)
                title_win.mvwin(0, 0)
                input_win.resize(2, new_x)  # Changed from 3
                input_win.mvwin(new_y - 2, 0)  # Changed position
                box_win.resize(1, new_x - 4)
                box_win.mvwin(new_y - 1, 2)  # Changed position
                
                # Update title
                title_win.clear()
                title_win.bkgd(' ', curses.color_pair(5) | curses.A_BOLD)
                title_win.addstr(0, (new_x - len(title_text)) // 2, title_text)
                
                # Redraw everything
                redraw_log_window()
                input_win.border()
                input_win.addstr(0, 2, " Command ")
                
                # Refresh all windows
                title_win.refresh()
                input_win.refresh()
                box_win.refresh()
            
            # Main input loop
            while self.running:
                try:
                    # Check for terminal resize
                    current_y, current_x = stdscr.getmaxyx()
                    if current_y != max_y or current_x != max_x:
                        max_y, max_x = current_y, current_x
                        handle_resize()
                        
                    # Process any pending log messages - increase priority of log processing
                    log_processed = False
                    while not self.log_queue.empty():
                        try:
                            log_message = self.log_queue.get_nowait()
                            log_messages.append(log_message)
                            log_processed = True
                        except queue.Empty:
                            break
                    
                    # Only redraw if we actually got new logs
                    if log_processed:
                        redraw_log_window()
                    
                    # Show prompt
                    box_win.clear()
                    box_win.refresh()
                    
                    # Get command with custom input handling
                    command = self._custom_input(box_win, max_x - 5)
                    
                    # Process the command
                    if command is not None:
                        process_command(command)
                    
                    # Redraw after command execution
                    redraw_log_window()
                    input_win.border()
                    input_win.addstr(0, 2, " Command ")
                    input_win.refresh()
                except curses.error:
                    # Handle curses errors, most likely from resize events
                    try:
                        max_y, max_x = stdscr.getmaxyx()
                        handle_resize()
                    except:
                        pass
        
        except Exception as e:
            self.logger.error(f"Error in curses UI: {str(e)}", exc_info=True)
        finally:
            # Clean up curses
            if 'stdscr' in locals():
                try:
                    # Reset the terminal to normal state
                    stdscr.keypad(False)
                    curses.nocbreak()
                    curses.echo()
                    curses.endwin()
                except:
                    # In case cleanup fails
                    pass
                    
            # Remove reference to prevent other methods from using it after cleanup
            if hasattr(self, '_curses_input_window'):
                delattr(self, '_curses_input_window')

    def _custom_input(self, win, width):
        """Custom input handler that supports command history and other special keys"""
        buffer = ""
        cursor_pos = 0
        history_index = len(self.command_history)
        
        def redraw_input():
            win.clear()
            # Handle case where buffer is longer than width
            if len(buffer) >= width:
                # Show portion of buffer around cursor
                display_start = max(0, cursor_pos - width//2)
                display_end = min(len(buffer), display_start + width)
                display_text = buffer[display_start:display_end]
                
                # Adjust cursor position for display
                adjusted_cursor = cursor_pos - display_start
                
                win.addstr(0, 0, display_text)
                win.move(0, adjusted_cursor)
            else:
                win.addstr(0, 0, buffer)
                win.move(0, cursor_pos)
            win.refresh()
        
        while True:
            redraw_input()
            
            try:
                key = win.getch()
                
                if key == ord('\n') or key == curses.KEY_ENTER:
                    # Enter key - submit command
                    return buffer
                
                elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                    # Backspace - delete character before cursor
                    if cursor_pos > 0:
                        buffer = buffer[:cursor_pos-1] + buffer[cursor_pos:]
                        cursor_pos -= 1
                
                elif key == curses.KEY_DC:
                    # Delete key - delete character at cursor
                    if cursor_pos < len(buffer):
                        buffer = buffer[:cursor_pos] + buffer[cursor_pos+1:]
                
                elif key == curses.KEY_LEFT:
                    # Move cursor left
                    if cursor_pos > 0:
                        cursor_pos -= 1
                
                elif key == curses.KEY_RIGHT:
                    # Move cursor right
                    if cursor_pos < len(buffer):
                        cursor_pos += 1
                
                elif key == curses.KEY_HOME:
                    # Move to start of line
                    cursor_pos = 0
                
                elif key == curses.KEY_END:
                    # Move to end of line
                    cursor_pos = len(buffer)
                
                elif key == curses.KEY_UP:
                    # Previous command in history
                    if self.command_history and history_index > 0:
                        history_index -= 1
                        buffer = self.command_history[history_index]
                        cursor_pos = len(buffer)
                
                elif key == curses.KEY_DOWN:
                    # Next command in history
                    if history_index < len(self.command_history) - 1:
                        history_index += 1
                        buffer = self.command_history[history_index]
                        cursor_pos = len(buffer)
                    elif history_index == len(self.command_history) - 1:
                        # At end of history, clear buffer
                        history_index = len(self.command_history)
                        buffer = ""
                        cursor_pos = 0
                
                elif key == 27:  # ESC
                    # Cancel input
                    return None
                
                elif key in (3, 4):  # Ctrl+C or Ctrl+D
                    # Handle exit keys
                    if key == 3:  # Ctrl+C
                        self.running = False
                        return "quit"
                    return None
                
                elif 32 <= key <= 126:  # Printable ASCII characters
                    # Insert character at cursor position
                    buffer = buffer[:cursor_pos] + chr(key) + buffer[cursor_pos:]
                    cursor_pos += 1
            
            except Exception as e:
                self.logger.error(f"Error in custom input handler: {str(e)}", exc_info=True)
                return None

    def signal_ready(self):
        """Signal that the console should start showing prompts"""
        self.ready_event.set()

    def show_welcome(self):
        """Display the welcome message (handled in start method)"""
        pass
    
    def stop(self):
        """Stop the console command input loop"""
        self.running = False
        if self.command_thread and self.command_thread.is_alive():
            self.logger.info("Stopping console command system")
    
    # Output capture class for command output
    class OutputCapture:
        def __init__(self, log_messages):
            self.log_messages = log_messages
        
        def write(self, text):
            if text.strip():  # Skip empty lines
                for line in text.splitlines():
                    if line.strip():
                        self.log_messages.append(line.rstrip())
        
        def flush(self):
            pass
    
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
        print("notify MSG - Send notification to all active chats")
        print("restart    - Restart the Telegram bot")
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
        
        # Ask for confirmation in a curses-compatible way
        if CURSES_AVAILABLE and self.command_thread and self.command_thread.is_alive():
            print("Are you sure you want to send this message?")
            print("Type 'y' or 'yes' to confirm, anything else to cancel.")
            confirmation = self._get_simple_input().lower()
        else:
            # Standard input for non-curses mode
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
        
        # Ask for confirmation in a curses-compatible way
        if CURSES_AVAILABLE and self.command_thread and self.command_thread.is_alive():
            print("Are you sure you want to restart the bot? Active users will be disconnected.")
            print("Type 'y' or 'yes' to confirm, anything else to cancel.")
            confirmation = self._get_simple_input().lower()
        else:
            # Standard input for non-curses mode
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

    def _get_simple_input(self):
        """Get simple text input in a curses-compatible way"""
        # Use the same custom input handler we use for commands
        if hasattr(self, '_curses_input_window') and self._curses_input_window:
            # If we already have a reference to the input window, use it
            return self._custom_input(self._curses_input_window, 20) or ""
        else:
            # Otherwise print a prompt and wait for manual input
            print("Enter response: ", end='', flush=True)
            return input()

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
