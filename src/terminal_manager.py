import os
import sys
import subprocess
import platform
import time
import signal
import threading
import psutil
from colorama import Fore, Style, init

# Ensure src is in the path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.logger import get_logger

class TerminalManager:
    """
    Manages multiple terminal windows for the application
    - Main terminal for commands
    - Log terminal for displaying logs
    """
    def __init__(self):
        self.logger = get_logger("terminal_manager")
        self.log_terminal_process = None
        self.main_terminal_pid = os.getpid()
        self.is_log_terminal = False
        self.log_terminal_started = threading.Event()
        
    def start_log_terminal(self):
        """Start a separate terminal window for logs"""
        if self.is_log_terminal:
            return False
        
        # Get path to log file
        logs_dir = os.path.join(parent_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "PolitoMensa.log")
            
        if platform.system() == "Windows":
            # Use PowerShell with proper escaping and quoting
            powershell_script = (
                '$host.ui.RawUI.WindowTitle = \\"PolitoMensa Logs\\"; '
                'Write-Host \\"\\n=== PolitoMensa Log Terminal ===\\nDisplaying application logs. Close this window to stop.\\n===================================\\n\\" -ForegroundColor Cyan; '
                f'Get-Content -Path \\"{log_file}\\" -Tail 20 -Wait'
            )
            
            cmd = f'start "PolitoMensa Logs" /D "{parent_dir}" powershell -NoExit -Command "{powershell_script}"'
            
            self.logger.debug(f"Windows command: {cmd}")
            shell = True
        elif platform.system() == "Darwin":  # macOS
            cmd = ['osascript', '-e', 
                  f'tell app "Terminal" to do script "echo \'\n=== PolitoMensa Log Terminal ===\nDisplaying application logs. Close this window to stop.\n===================================\n\' && tail -n 20 -f {log_file}"']
            shell = False
        else:  # Linux
            if self._command_exists("gnome-terminal"):
                cmd = f'gnome-terminal --title="PolitoMensa Logs" -- bash -c "echo -e \'\n=== PolitoMensa Log Terminal ===\nDisplaying application logs. Close this window to stop.\n===================================\n\' && tail -n 20 -f {log_file}"'
                shell = True
            elif self._command_exists("xterm"):
                cmd = f'xterm -title "PolitoMensa Logs" -hold -e "echo -e \'\n=== PolitoMensa Log Terminal ===\nDisplaying application logs. Close this window to stop.\n===================================\n\' && tail -n 20 -f {log_file}"'
                shell = True

        try:
            # Start the log terminal
            self.logger.info(f"Starting log terminal with command: {cmd}")
            if shell:
                self.log_terminal_process = subprocess.Popen(cmd, shell=True)
            else:
                self.log_terminal_process = subprocess.Popen(cmd)
                
            # Wait briefly to ensure terminal starts
            time.sleep(1)
            
            # Set an event to indicate log terminal has started
            self.log_terminal_started.set()
            
            # Mark this as the main terminal so the logger respects it
            os.environ["POLITOMENSA_MAIN_TERMINAL"] = "1"
            
            # Remove all console output from main terminal
            self._suppress_main_terminal_logs()
            
            self.logger.info("Log terminal started successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error starting log terminal: {e}")
            return False
    
    def _suppress_main_terminal_logs(self):
        """Suppress logs (but not console output) in the main terminal"""
        import logging
        
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Remove any console handlers from all loggers
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            for handler in list(logger.handlers):
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    logger.removeHandler(handler)
        
        # Also remove console handlers from root logger
        for handler in list(root_logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                root_logger.removeHandler(handler)
        
        # Add a NullHandler to suppress any new handlers that might be added
        root_logger.addHandler(logging.NullHandler())
        
        # DO NOT redirect stdout/stderr as it will prevent console interaction
        # Instead, just add the environment variable to signal main terminal status
        os.environ["POLITOMENSA_MAIN_TERMINAL"] = "1"
        
        # We can't log this as logging is now suppressed
        # self.logger.debug("Suppressed logs in main terminal")
        
    def run_as_log_terminal(self):
        """Run the current process as a log terminal"""
        self.is_log_terminal = True
        print("\n=== PolitoMensa Log Terminal ===")
        print("Displaying application logs. Close this window to stop.")
        print("=====================================\n")
        
        # Just output logs from the log file
        self.logger.info("Log terminal is active")
        
        try:
            # Keep terminal open until closed
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Log terminal closed by user")
        
        return True
        
    def cleanup(self):
        """Clean up resources when application is shutting down"""
        if self.log_terminal_process:
            try:
                # Get the process group
                process = psutil.Process(self.log_terminal_process.pid)
                children = process.children(recursive=True)
                
                # Terminate children first
                for child in children:
                    child.terminate()
                
                # Terminate the main process
                process.terminate()
                
                self.logger.info(f"{Fore.GREEN}Terminated log terminal process{Style.RESET_ALL}")
            except Exception as e:
                self.logger.error(f"{Fore.RED}Error terminating log terminal: {str(e)}{Style.RESET_ALL}")
    
    def _command_exists(self, command):
        """Check if a command exists on the system PATH"""
        try:
            subprocess.call([command, "--version"], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
