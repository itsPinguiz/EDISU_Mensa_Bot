from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import asyncio
from src.logger import get_logger
from src.credentials import get_telegram_token

class Telebot:
    def __init__(self, app):
        self.app = app
        self.logger = get_logger()
        self.logger.info("Initializing Telegram bot")
        
        self.token = self._get_telegram_token()
        self.logger.debug("Building Telegram application")
        self.application = ApplicationBuilder().token(self.token).build()
        
        # Register handlers
        self._register_handlers()
    
    def _get_telegram_token(self):
        """Get the Telegram bot token from secure storage"""
        self.logger.debug("Getting Telegram bot token from secure storage")
        try:
            return get_telegram_token()
        except ValueError as e:
            self.logger.error(f"Failed to get Telegram token: {str(e)}")
            raise
    
    def _register_handlers(self):
        """Register command and callback handlers"""
        self.logger.debug("Registering handlers")
        
        # Command handlers (still needed for initial interaction)
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Add callback query handler for button clicks
        self.application.add_handler(CallbackQueryHandler(self.handle_button))
        
        self.logger.info("Command and callback handlers registered successfully")
    
    def _is_meal_type_available(self, meal_type):
        """Check if any cafeterias have menus for this meal type"""
        for cafeteria in self.app.instagram.cafeterias:
            menu = self.app.get_menu(cafeteria, meal_type)
            # Check if this is not a placeholder or error message
            if not any(msg in menu for msg in ["not available", "Error fetching"]):
                return True
        return False
    
    def _is_menu_available(self, cafeteria, meal_type):
        """Check if a specific cafeteria has a menu for the specified meal type"""
        menu = self.app.get_menu(cafeteria, meal_type)
        
        # Expanded list of strings that indicate an unavailable menu
        unavailable_indicators = [
            "not available", 
            "Error fetching",
            "Menu not available",
            f"Menu {meal_type} not available"
        ]
        
        # Check for specific indicators of an empty menu
        if any(indicator in menu for indicator in unavailable_indicators):
            return False
            
        # Check if this is just a placeholder menu
        if "placeholder" in menu.lower() or "menu for" in menu.lower():
            return False
            
        # If menu is too short, it's probably not a real menu
        if len(menu.strip()) < 50:  # Real menus should be longer than this
            return False
            
        return True
    
    def _get_main_keyboard(self):
        """Create the main keyboard with meal type options, only showing available ones"""
        keyboard = []
        
        meal_buttons = []
        if self._is_meal_type_available("pranzo"):
            meal_buttons.append(InlineKeyboardButton("🥄 Menù Pranzo", callback_data="meal_pranzo"))
        if self._is_meal_type_available("cena"):
            meal_buttons.append(InlineKeyboardButton("🍽️ Menù Cena", callback_data="meal_cena"))
        
        if meal_buttons:
            keyboard.append(meal_buttons)
        
        # Always show these options
        keyboard.append([
            InlineKeyboardButton("📋 Tutti i menù", callback_data="all_menus"),
            InlineKeyboardButton("🔄 Aggiorna menù", callback_data="update_menus"),
        ])
        keyboard.append([
            InlineKeyboardButton("❓ Aiuto", callback_data="help"),
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _get_cafeteria_keyboard(self, meal_type):
        """Create keyboard with cafeteria selection for specified meal type, showing only available ones"""
        keyboard = []
        
        # Filter cafeterias with available menus for this meal type
        available_cafeterias = []
        for cafeteria in self.app.instagram.cafeterias:
            if self._is_menu_available(cafeteria, meal_type):
                available_cafeterias.append(cafeteria)
        
        # Group cafeterias in pairs for better UI
        for i in range(0, len(available_cafeterias), 2):
            row = []
            cafeteria_name = available_cafeterias[i]
            display_name = cafeteria_name
            if cafeteria_name == "Perrone":
                display_name = "Perrone (Novara)"
                
            row.append(InlineKeyboardButton(
                display_name, 
                callback_data=f"menu_{meal_type}_{cafeteria_name}"
            ))
            
            # Add second cafeteria in the row if it exists
            if i + 1 < len(available_cafeterias):
                cafeteria_name = available_cafeterias[i+1]
                display_name = cafeteria_name
                if cafeteria_name == "Perrone":
                    display_name = "Perrone (Novara)"
                    
                row.append(InlineKeyboardButton(
                    display_name, 
                    callback_data=f"menu_{meal_type}_{cafeteria_name}"
                ))
            
            keyboard.append(row)
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("« Torna al menu principale", callback_data="back_to_main")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _get_back_keyboard(self):
        """Create a simple keyboard with just a back button"""
        keyboard = [[InlineKeyboardButton("« Torna al menu principale", callback_data="back_to_main")]]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message with menu buttons when /start is issued."""
        user = update.effective_user
        self.logger.info(f"Start command received from user {user.id} ({user.username})")
        
        welcome_text = (
            "Benvenuto nel Bot Mensa Polito!\n\n"
            "Questo bot ti permette di consultare i menù delle mense "
            "universitarie di Polito. Seleziona un'opzione:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self._get_main_keyboard()
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help information when /help is issued."""
        user = update.effective_user
        self.logger.info(f"Help command received from user {user.id} ({user.username})")
        
        help_text = (
            "Usa i pulsanti qui sotto per interagire con il bot:\n\n"
            "• *Menù Pranzo* - Visualizza i menù di pranzo\n"
            "• *Menù Cena* - Visualizza i menù di cena\n"
            "• *Tutti i menù* - Visualizza tutti i menù disponibili\n"
            "• *Aggiorna menù* - Forza l'aggiornamento dei menù odierni\n\n"
            "Dopo aver scelto pranzo o cena, potrai selezionare la mensa specifica."
        )
        
        await update.message.reply_text(
            help_text,
            reply_markup=self._get_main_keyboard(),
            parse_mode="Markdown"
        )
    
    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks (callback queries)"""
        query = update.callback_query
        user = query.from_user
        callback_data = query.data
        
        # Always answer the callback query to stop the loading animation
        await query.answer()
        
        self.logger.info(f"Button click from user {user.id} ({user.username}): {callback_data}")
        
        if callback_data.startswith("meal_"):
            # User selected a meal type (pranzo/cena)
            meal_type = callback_data[5:]  # Remove "meal_" prefix
            await self._show_cafeteria_selection(query, meal_type)
        elif callback_data == "all_menus":
            await self._show_all_menus(query)
        elif callback_data == "update_menus":
            await self._update_menus(query)
        elif callback_data == "help":
            await self._show_help(query)
        elif callback_data == "back_to_main":
            await self._back_to_main_menu(query)
        elif callback_data.startswith("menu_"):
            # Extract meal type and cafeteria name from callback data
            # Format: menu_[meal_type]_[cafeteria]
            parts = callback_data[5:].split("_", 1)
            if len(parts) == 2:
                meal_type, cafeteria = parts
                await self._show_cafeteria_menu(query, cafeteria, meal_type)
            else:
                # For backward compatibility
                await self._show_cafeteria_menu(query, callback_data[5:], "pranzo")
    
    async def _show_cafeteria_selection(self, query, meal_type):
        """Show cafeteria selection for the chosen meal type, handling no available menus case"""
        self.logger.info(f"Showing cafeteria selection for {meal_type} to user {query.from_user.id}")
        
        # Check if any cafeterias have menus for this meal type
        cafeterias_available = False
        for cafeteria in self.app.instagram.cafeterias:
            if self._is_menu_available(cafeteria, meal_type):
                cafeterias_available = True
                break
        
        meal_name = "Pranzo" if meal_type == "pranzo" else "Cena"
        
        if cafeterias_available:
            await query.edit_message_text(
                f"Seleziona una mensa per visualizzare il menù di *{meal_name}*:",
                reply_markup=self._get_cafeteria_keyboard(meal_type),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"*Nessun menù di {meal_name} disponibile oggi.*\n\n"
                f"Riprova più tardi o aggiorna i menù.",
                reply_markup=self._get_back_keyboard(),
                parse_mode="Markdown"
            )
    
    async def _show_cafeteria_menu(self, query, cafeteria, meal_type="pranzo"):
        """Show menu for a specific cafeteria and meal type"""
        self.logger.info(f"Showing {cafeteria} {meal_type} menu to user {query.from_user.id}")
        
        # Get menu specifying meal type
        menu = self.app.get_menu(cafeteria, meal_type)
        meal_name = "Pranzo" if meal_type == "pranzo" else "Cena"
        menu_text = f"*Menù {meal_name} - {cafeteria}*\n\n{menu}"
        
        await query.edit_message_text(
            menu_text,
            reply_markup=self._get_back_keyboard(),
            parse_mode="Markdown"
        )
    
    async def _show_all_menus(self, query):
        """Show all cafeteria menus"""
        self.logger.info(f"Showing all menus selection to user {query.from_user.id}")
        
        # First, ask which meal type to show
        keyboard = [
            [
                InlineKeyboardButton("🥄 Tutti i menù pranzo", callback_data="all_pranzo"),
                InlineKeyboardButton("🍽️ Tutti i menù cena", callback_data="all_cena"),
            ],
            [
                InlineKeyboardButton("« Torna al menu principale", callback_data="back_to_main")
            ]
        ]
        
        await query.edit_message_text(
            "Seleziona quale tipo di menù vuoi visualizzare:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _show_all_menus_by_type(self, query, meal_type):
        """Show all cafeteria menus for a specific meal type"""
        meal_name = "Pranzo" if meal_type == "pranzo" else "Cena"
        self.logger.info(f"Showing all {meal_name} menus to user {query.from_user.id}")
        
        await query.edit_message_text(
            f"Recupero i menù di {meal_name} per tutte le mense...",
            reply_markup=None
        )
        
        # Get all cafeteria menus
        cafeterias = ["Principe Amedeo", "Castelfidardo", "Paolo Borsellino", "Perrone"]
        
        # First edit the original message
        await query.edit_message_text(
            f"Ecco i menù di {meal_name} per tutte le mense:",
            reply_markup=self._get_back_keyboard()
        )
        
        # Send each menu as a separate message
        for cafeteria in cafeterias:
            menu = self.app.get_menu(cafeteria, meal_type)
            menu_text = f"{menu}"
            
            # Send new message for each menu
            await query.message.reply_text(
                menu_text, 
                parse_mode="Markdown"
            )
            
            # Add a small delay to avoid rate limits
            await asyncio.sleep(0.5)
    
    async def _update_menus(self, query):
        """Force update menus"""
        self.logger.info(f"Updating menus at request of user {query.from_user.id}")
        
        await query.edit_message_text(
            "Aggiornamento dei menù in corso... Attendere prego.",
            reply_markup=None
        )
        
        # Check for Tesseract
        tesseract_available = False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            tesseract_available = True
        except:
            tesseract_available = False
        
        try:
            menus = self.app.fetch_daily_menus()
            
            if menus:
                self.logger.info("Menus updated successfully via user request")
                
                success_message = "I menù sono stati aggiornati con successo!"
                
                if not tesseract_available:
                    success_message += "\n\n⚠️ *Nota*: Tesseract OCR non è installato, quindi vengono mostrati menù generici. Per estrarre i menù reali, installa Tesseract OCR."
                
                await query.edit_message_text(
                    success_message,
                    reply_markup=self._get_main_keyboard(),
                    parse_mode="Markdown"
                )
            else:
                self.logger.warning("Menu update returned empty result")
                await query.edit_message_text(
                    "Aggiornamento non riuscito. Riprova più tardi.",
                    reply_markup=self._get_main_keyboard()
                )
        except Exception as e:
            self.logger.error(f"Error during user-requested menu update: {str(e)}", exc_info=True)
            await query.edit_message_text(
                "Si è verificato un errore durante l'aggiornamento dei menù. Riprova più tardi.",
                reply_markup=self._get_main_keyboard()
            )
    
    async def _show_help(self, query):
        """Show help information"""
        help_text = (
            "Usa i pulsanti qui sotto per interagire con il bot:\n\n"
            "• *Menù Pranzo* - Visualizza i menù di pranzo\n"
            "• *Menù Cena* - Visualizza i menù di cena\n"
            "• *Tutti i menù* - Visualizza tutti i menù disponibili\n"
            "• *Aggiorna menù* - Forza l'aggiornamento dei menù odierni\n\n"
            "Dopo aver scelto pranzo o cena, potrai selezionare la mensa specifica."
        )
        
        await query.edit_message_text(
            help_text,
            reply_markup=self._get_main_keyboard(),
            parse_mode="Markdown"
        )
    
    async def _back_to_main_menu(self, query):
        """Return to main menu"""
        await query.edit_message_text(
            "Menu principale del Bot Mensa Polito.\nSeleziona un'opzione:",
            reply_markup=self._get_main_keyboard()
        )
    
    async def _setup_menu_button(self):
        """Configure the bot's menu button to show commands"""
        try:
            # Set up commands that will appear in the menu
            commands = [
                ("start", "Avvia il bot e mostra il menu principale"),
                ("help", "Mostra informazioni di aiuto")
            ]
            
            # Set the commands for this bot
            await self.application.bot.set_my_commands(commands)
            
            # Configure the menu button to show commands
            await self.application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            
            self.logger.info("Chat menu button configured to show commands")
        except Exception as e:
            self.logger.error(f"Failed to configure menu button: {str(e)}")

    async def _clear_chat_history(self):
        """Attempt to clear previous chats by sending a reset message"""
        try:
            # Get all active chats from the bot
            updates = await self.application.bot.get_updates(offset=-1, limit=100)
            
            # Extract unique chat IDs
            chat_ids = set()
            for update in updates:
                if update.message and update.message.chat:
                    chat_ids.add(update.message.chat.id)
                elif update.callback_query and update.callback_query.message.chat:
                    chat_ids.add(update.callback_query.message.chat.id)
            
            # Send restart notification to each chat
            restart_message = "🔄 *Bot riavviato*\nTutti i menu sono stati reimpostati. Usa i pulsanti qui sotto per ricominciare."
            for chat_id in chat_ids:
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=restart_message,
                        parse_mode="Markdown",
                        reply_markup=self._get_main_keyboard()
                    )
                    self.logger.info(f"Sent restart notification to chat {chat_id}")
                except Exception as e:
                    self.logger.warning(f"Could not send restart notification to chat {chat_id}: {str(e)}")
            
            self.logger.info(f"Sent restart notifications to {len(chat_ids)} chats")
        except Exception as e:
            self.logger.error(f"Error clearing chat history: {str(e)}")

    def run(self, debug=False):
        """Start the bot."""
        self.logger.info(f"Starting Telegram bot with polling (debug={debug})")
        
        # Use a single event loop for all async operations
        import asyncio
        
        async def startup():
            """Initialize and start the Telegram bot"""
            try:
                # Initialize the application
                await self.application.initialize()
                
                # Set up menu button
                await self._setup_menu_button()
                
                # Clear previous chats
                await self._clear_chat_history()
                
                # Start the bot and polling
                await self.application.start()
                await self.application.updater.start_polling()
                
                self.logger.info("Bot started and polling for updates")
                
                # Keep the bot running until manually stopped
                # Instead of stop_on_signal(), use a simple approach to keep the bot running
                stop_event = asyncio.Event()
                
                # The following will keep the task alive until the bot is stopped
                await stop_event.wait()
                
            except Exception as e:
                self.logger.error(f"Error during bot operation: {str(e)}", exc_info=True)
            finally:
                # Ensure proper shutdown
                try:
                    # Only try to stop and shutdown if we've initialized
                    if hasattr(self.application, 'updater') and self.application.updater.running:
                        await self.application.updater.stop()
                    if hasattr(self.application, 'running') and self.application.running:
                        await self.application.stop()
                    await self.application.shutdown()
                    self.logger.info("Bot has been properly shut down")
                except Exception as e:
                    self.logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        
        # Run everything in a single event loop
        try:
            asyncio.run(startup())
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user (KeyboardInterrupt)")
        except Exception as e:
            self.logger.error(f"Bot stopped due to error: {str(e)}", exc_info=True)
