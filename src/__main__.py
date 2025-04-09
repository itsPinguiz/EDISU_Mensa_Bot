import argparse
import sys
import signal
import os

# Fix import paths to work in all scenarios
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PolitoMensa Bot")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-console", "-nc", action="store_true", help="Disable console commands")
    parser.add_argument("--console-only", "-co", action="store_true", help="Start console without other components")
    parser.add_argument("--log-terminal", action="store_true", help="Run as log terminal")
    parser.add_argument("--single-terminal", "-st", action="store_true", help="Use single terminal mode")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode with placeholder menus")
    args = parser.parse_args()
    
    # Configure logging based on arguments
    if args.debug:
        os.environ["POLITOMENSA_LOG_LEVEL"] = "DEBUG"
    
    if args.single_terminal:
        os.environ["POLITOMENSA_SINGLE_TERMINAL"] = "1"
    
    if args.log_terminal:
        # Running as log terminal - initialize and run
        try:
            print("Initializing log terminal...")
            # Set this before any logging happens
            os.environ["POLITOMENSA_LOG_TERMINAL"] = "1"
            from src.terminal_manager import TerminalManager
            terminal_manager = TerminalManager()
            terminal_manager.run_as_log_terminal()
            sys.exit(0)
        except Exception as e:
            print(f"Error starting log terminal: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Import app and start based on arguments
    from src.app import App
    from src.terminal_manager import TerminalManager

    # Create terminal manager for multi-terminal mode
    terminal_manager = None
    if not args.single_terminal and not args.no_console:
        terminal_manager = TerminalManager()
        
        # Set up cleanup on exit
        def cleanup_handler(signum, frame):
            if terminal_manager:
                terminal_manager.cleanup()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, cleanup_handler)
        signal.signal(signal.SIGTERM, cleanup_handler)
        
        # Start log terminal before any other logging occurs
        terminal_manager.start_log_terminal()
    
    # Create and run the application
    app = App()
    
    if args.console_only:
        # Start just the console
        app.run_console_only()
    else:
        # Start everything
        app.run(debug=args.debug, enable_console=not args.no_console, demo_mode=args.demo)
        
    # Clean up terminal manager on exit
    if terminal_manager:
        terminal_manager.cleanup()
