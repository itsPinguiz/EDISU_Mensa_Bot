from instagrapi import Client
from typing import Dict, List, Optional, Tuple
import os
import re
import logging
import tempfile
from datetime import datetime
import pytesseract
from PIL import Image
import io
import requests
from src.logger import get_logger
from src.credentials import get_instagram_credentials

class InstApi:
    def __init__(self, app):
        self.app = app
        self.logger = get_logger()
        self.logger.info("Initializing Instagram API client")
        self.client = Client()
        self.logged_in = False
        
        # Set the correct cafeteria account
        self.cafeteria_account = "edisu_piemonte"
        
        # Update cafeteria names to match official names
        self.cafeterias = [
            "Principe Amedeo",  # Previously "Central"
            "Castelfidardo",    # Keep same name
            "Paolo Borsellino", # Previously "Sobrero"
            "Perrone"           # Previously "Corso Duca"
        ]
        
        # Mapping of old names to new names (for backward compatibility)
        self.name_mapping = {
            "Central": "Principe Amedeo",
            "Sobrero": "Paolo Borsellino",
            "Corso Duca": "Perrone"
        }
        
        # Updated keywords to identify cafeterias in OCR text
        self.cafeteria_keywords = {
            "Principe Amedeo": ["principe amedeo", "central", "centro", "via principe"],
            "Castelfidardo": ["castelfidardo", "castel", "politecnico", "politecnico castelfidardo"],
            "Paolo Borsellino": ["borsellino", "sobrero", "paolo borsellino"],
            "Perrone": ["perrone", "novara", "corso duca", "corso"]
        }
        
        # Updated menu section headers to better match the Instagram posts
        self.section_headers = {
            "primi": ["primi piatti", "primi", "primo piatto", "primo"],
            "secondi": ["secondi piatti", "secondi", "secondo piatto", "secondo"],
            "contorni": ["contorni", "contorno"],
            "dessert": ["dessert", "dolci", "frutta", "dolce"]
        }
        
        # Define the correct menu section order
        self.section_order = ["primi", "secondi", "contorni", "dessert"]
        
        # Food item terms by category to help with classification
        self.food_items_by_section = {
            "primi": ["pasta", "risotto", "zuppa", "minestra", "gnocchi", "lasagne", "cannelloni", 
                     "spaghetti", "gazpacho", "riso", "ravioli"],
            "secondi": ["pollo", "tacchino", "manzo", "maiale", "vitello", "pesce", "tonno", 
                       "merluzzo", "brie", "formaggio", "uova", "frittata", "arrosto", "spezzatino"],
            "contorni": ["insalata", "patate", "verdure", "carote", "zucchine", "broccoli", 
                        "spinaci", "bietole", "zucca", "fagiolini"],
            "dessert": ["torta", "gelato", "budino", "yogurt", "crostata", "frutta", "mela", 
                       "pera", "arancia", "banana", "cioccolato"]
        }
        
        self.meal_keywords = {
            "pranzo": ["pranzo", "lunch", "mezzogiorno"],
            "cena": ["cena", "dinner", "sera"]
        }
        
        self.logger.debug(f"Configured to fetch menus for {len(self.cafeterias)} cafeterias from account: {self.cafeteria_account}")
        
    def login(self):
        """Login to Instagram using secure credentials"""
        self.logger.info("Logging in to Instagram")
        
        try:
            # Get credentials from secure storage
            username, password = get_instagram_credentials()
            
            self.logger.debug(f"Attempting login with username: {username}")
            self.client.login(username, password)
            self.logged_in = True
            self.logger.info("Successfully logged in to Instagram")
            return True
        except Exception as e:
            self.logger.error(f"Instagram login failed: {str(e)}", exc_info=True)
            return False
    
    def fetch_menus(self) -> Dict[str, Dict[str, str]]:
        """Fetch menus from Instagram stories"""
        self.logger.info("Fetching menus from Instagram stories")
        if not self.logged_in:
            self.logger.warning("Not logged in to Instagram, attempting login")
            login_success = self.login()
            if not login_success:
                self.logger.error("Login failed, cannot fetch menus")
                return {}
        
        menus = {}
        # Initialize with empty menus for all cafeterias
        for cafeteria in self.cafeterias:
            menus[cafeteria] = {
                "pranzo": "Menu pranzo not available",
                "cena": "Menu cena not available"
            }
        
        try:
            # Get user ID from username
            user_id = self.client.user_id_from_username(self.cafeteria_account)
            self.logger.debug(f"Found user ID for {self.cafeteria_account}: {user_id}")
            
            # Get user's stories
            self.logger.debug(f"Fetching stories for user {user_id}")
            stories = self.client.user_stories(user_id)
            
            if stories:
                self.logger.info(f"Found {len(stories)} stories")
                
                # Check if Tesseract is available
                tesseract_available = self._check_tesseract()
                
                if tesseract_available:
                    # Process all stories from today to find menus for different cafeterias
                    extracted_menus = self._extract_menus_from_stories(stories)
                    
                    # Update menus with what we found
                    for cafeteria, menu_data in extracted_menus.items():
                        if cafeteria in menus:
                            menus[cafeteria] = menu_data
                            self.logger.debug(f"Updated menus for {cafeteria}")
                    
                    # Check if we're missing any cafeteria menus
                    missing_cafeterias = []
                    for cafe in self.cafeterias:
                        if menus[cafe]["pranzo"] == "Menu pranzo not available" and menus[cafe]["cena"] == "Menu cena not available":
                            missing_cafeterias.append(cafe)
                    
                    if missing_cafeterias:
                        self.logger.warning(f"Could not find menus for: {', '.join(missing_cafeterias)}")
                        # Fill in missing menus with placeholders
                        for cafeteria in missing_cafeterias:
                            menus[cafeteria]["pranzo"] = self._generate_placeholder_menu(cafeteria, "pranzo")
                            menus[cafeteria]["cena"] = self._generate_placeholder_menu(cafeteria, "cena")
                            self.logger.info(f"Generated placeholder menus for {cafeteria}")
                else:
                    # Tesseract not available, use placeholder menus
                    self.logger.warning("Tesseract OCR not available, using placeholder menus")
                    for cafeteria in self.cafeterias:
                        menus[cafeteria]["pranzo"] = self._generate_placeholder_menu(cafeteria, "pranzo")
                        menus[cafeteria]["cena"] = self._generate_placeholder_menu(cafeteria, "cena")
                        self.logger.info(f"Generated placeholder menus for {cafeteria}")
            else:
                self.logger.warning(f"No stories found for {self.cafeteria_account}")
                for cafeteria in self.cafeterias:
                    menus[cafeteria]["pranzo"] = "No menu posted today"
                    menus[cafeteria]["cena"] = "No menu posted today"
        except Exception as e:
            self.logger.error(f"Error fetching menus: {str(e)}", exc_info=True)
            for cafeteria in self.cafeterias:
                menus[cafeteria] = {
                    "pranzo": f"Error fetching pranzo menu: {str(e)}",
                    "cena": f"Error fetching cena menu: {str(e)}"
                }
        
        self.logger.info(f"Completed menu fetch for {len(menus)} cafeterias")
        return menus
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available"""
        try:
            # Try importing and configuring first
            from src.ocr_utils import configure_tesseract
            configure_tesseract()
            
            # Now try to get version
            import pytesseract
            pytesseract.get_tesseract_version()
            self.logger.debug("Tesseract OCR is available")
            return True
        except Exception as e:
            # Check if we're on PythonAnywhere
            if "PYTHONANYWHERE_SITE" in os.environ:
                self.logger.info("Running on PythonAnywhere, will use cloud OCR service")
                # Check if cloud OCR is configured
                if os.environ.get("OCR_API_KEY"):
                    return False  # We'll use cloud OCR
                else:
                    self.logger.warning("Cloud OCR API key not configured")
            else:
                self.logger.warning(f"Tesseract OCR is not available: {str(e)}")
            return False
    
    def _extract_menus_from_stories(self, stories) -> Dict[str, Dict[str, str]]:
        """
        Extract menus for all cafeterias from the stories using OCR
        """
        self.logger.debug(f"Extracting menus from {len(stories)} stories")
        extracted_menus = {}
        
        # Initialize structure for all cafeterias
        for cafeteria in self.cafeterias:
            extracted_menus[cafeteria] = {
                "pranzo": "",
                "cena": ""
            }
        
        # Process all stories first to extract text
        story_texts = []
        for i, story in enumerate(stories):
            story_id = getattr(story, 'id', f'story_{i}')
            self.logger.debug(f"Processing story {story_id}")
            
            # Get OCR text from story
            ocr_text = self._extract_text_from_story(story)
            if not ocr_text:
                self.logger.warning(f"Could not extract text from story {story_id}")
                continue
            
            story_texts.append((story_id, ocr_text))
        
        # Now process the extracted texts to identify cafeterias and meals
        for story_id, ocr_text in story_texts:
            # Determine which cafeteria this story is for
            cafeteria = self._identify_cafeteria_from_text(ocr_text, extracted_menus)
            if not cafeteria:
                self.logger.debug(f"Could not identify cafeteria for story {story_id}")
                continue
                
            # Try to identify if this is lunch or dinner
            meal_type = self._identify_meal_type(ocr_text)
            
            # Process the menu text to clean it up
            menu_text = self._process_menu_text(ocr_text, cafeteria, meal_type)
            
            # Store the menu
            if extracted_menus[cafeteria][meal_type]:
                self.logger.debug(f"Already have a {meal_type} menu for {cafeteria}, checking quality")
                # If we already have a menu for this meal, keep the better one (longer text usually means more content)
                if len(menu_text) > len(extracted_menus[cafeteria][meal_type]):
                    extracted_menus[cafeteria][meal_type] = menu_text
                    self.logger.info(f"Updated {meal_type} menu for {cafeteria} from story {story_id}")
            else:
                extracted_menus[cafeteria][meal_type] = menu_text
                self.logger.info(f"Extracted {meal_type} menu for {cafeteria} from story {story_id}")
        
        return extracted_menus
    
    def _identify_meal_type(self, text: str) -> str:
        """Identify if this is a lunch or dinner menu"""
        text_lower = text.lower()
        
        for meal_type, keywords in self.meal_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    self.logger.debug(f"Identified meal type as {meal_type}")
                    return meal_type
        
        # Default to lunch if not specified
        return "pranzo"
    
    def _extract_text_from_story(self, story) -> str:
        """Extract text from a story image using OCR"""
        # Check if Tesseract is available
        tesseract_available = self._check_tesseract()
        
        try:
            # Get the story image
            if hasattr(story, 'thumbnail_url') and story.thumbnail_url:
                media_url = story.thumbnail_url
            elif hasattr(story, 'media_urls') and story.media_urls:
                media_url = story.media_urls[0]
            else:
                self.logger.debug("Downloading story media using instagrapi")
                story_path = self.client.story_download(story.pk)
                if story_path:
                    with open(story_path, 'rb') as f:
                        image = Image.open(io.BytesIO(f.read()))
                    if os.path.exists(story_path):
                        os.remove(story_path)
                else:
                    self.logger.error(f"Failed to download story {story.pk}")
                    return ""
            
            if 'media_url' in locals():
                self.logger.debug(f"Downloading image from URL: {media_url}")
                response = requests.get(media_url)
                if response.status_code == 200:
                    image = Image.open(io.BytesIO(response.content))
                else:
                    self.logger.error(f"Failed to download image: {response.status_code}")
                    return ""
            
            if tesseract_available:
                self.logger.debug("Running OCR with Tesseract")
                text = pytesseract.image_to_string(image, lang='ita')
            else:
                self.logger.debug("Running OCR with cloud service")
                from src.cloud_ocr import extract_text_from_image_cloud
                text = extract_text_from_image_cloud(image)
            
            self.logger.debug(f"OCR extracted {len(text)} characters")
            return text
        except Exception as e:
            self.logger.error(f"Error extracting text from story: {str(e)}", exc_info=True)
            return ""
    
    def _identify_cafeteria_from_text(self, text: str, existing_menus: Dict[str, Dict[str, str]] = None) -> Optional[str]:
        """
        Identify which cafeteria a story is for based on keywords in the text
        
        Args:
            text: The OCR text to analyze
            existing_menus: Dictionary of already identified cafeteria menus
            
        Returns:
            Cafeteria name or None if not identified
        """
        if not text:
            return None
            
        # Initialize empty dict if None is passed
        if existing_menus is None:
            existing_menus = {}
        
        # Split text into lines and get the first line which should contain "Mensa [name]"
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text_lower = text.lower()
        
        # First check if the structure matches "Mensa [name]" in the first lines
        for i, line in enumerate(lines[:3]):  # Check first 3 lines (in case of OCR errors)
            line_lower = line.lower()
            if "mensa" in line_lower:
                self.logger.debug(f"Found 'Mensa' reference in line: {line}")
                # Extract cafeteria name from this line
                for cafeteria, keywords in self.cafeteria_keywords.items():
                    for keyword in keywords:
                        if keyword in line_lower:
                            self.logger.info(f"Identified cafeteria {cafeteria} from line: {line}")
                            return cafeteria
        
        # If not found in first line, check the entire text for cafeteria keywords
        for cafeteria, keywords in self.cafeteria_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    self.logger.debug(f"Identified cafeteria {cafeteria} from keyword '{keyword}'")
                    return cafeteria
        
        # If no clear match, try to make an educated guess
        self.logger.warning("Could not identify cafeteria from keywords, attempting content analysis")
        
        # Verify this is actually a menu
        menu_indicators = ["primi piatti", "secondi piatti", "contorni", "menù", "pranzo", "cena"]
        if any(indicator in text_lower for indicator in menu_indicators):
            # This is likely a menu but we can't determine which cafeteria
            # Assign to the first cafeteria without a menu
            for cafeteria in self.cafeterias:
                if cafeteria not in existing_menus:
                    self.logger.debug(f"Assigning menu to {cafeteria} based on menu indicators")
                    return cafeteria
        
        return None
    
    def _process_menu_text(self, text: str, cafeteria: str, meal_type: str = "pranzo") -> str:
        """Process and clean up the extracted menu text with simpler line-by-line processing"""
        self.logger.debug(f"Processing {meal_type} menu text for {cafeteria} ({len(text)} chars)")
        
        # Split the text into lines and remove empty lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Format more concisely - removed redundant emoji header
        from datetime import datetime
        today = datetime.now().strftime("%d/%m/%Y")
        
        # Create a more concise header
        result_lines = []
        # Add only the date without repeating the cafeteria name which is shown in the UI
        result_lines.append(f"*{today}*")
        result_lines.append("")  # Empty line after metadata
        
        # Process lines and identify menu sections
        sections_data = {'primi': [], 'secondi': [], 'contorni': []}
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip header lines that we've already processed
            if any(keyword in line_lower for keyword in 
                  ["mensa", "menù", "menu", "data", "edisu", "piemonte"]):
                continue
            
            # Check if this line is a section header
            is_section_header = False
            new_section = None
            
            for section, headers in self.section_headers.items():
                if any(header in line_lower for header in headers):
                    new_section = section
                    is_section_header = True
                    break
            
            # If we found a section header, switch to that section
            if is_section_header:
                current_section = new_section
            # If this line is not a section header and we have a current section, it's a dish
            elif current_section and current_section in sections_data:
                # Add dish to the current section (if it's not too short to be a real dish)
                if len(line) > 3:  # Avoid very short lines that are probably OCR errors
                    sections_data[current_section].append(line)
        
        # Format each section with dishes
        for section in self.section_order[:-1]:  # Skip dessert as we'll add it manually
            if section in sections_data and sections_data[section]:
                section_emoji = self._get_section_emoji(section)
                result_lines.append(f"{section_emoji} *{section.upper()}* {section_emoji}")
                
                for dish in sections_data[section]:
                    # Convert to sentence case (first letter capital, rest lowercase)
                    dish_text = dish.lower()
                    if dish_text:
                        dish_text = dish_text[0].upper() + dish_text[1:]
                    result_lines.append(f"• {dish_text}")
                
                result_lines.append("")  # Empty line between sections
        
        # Always add dessert section with standard options
        dessert_emoji = self._get_section_emoji("dessert")
        result_lines.append(f"{dessert_emoji} *DESSERT* {dessert_emoji}")
        result_lines.append("• Frutta fresca")
        result_lines.append("• Dessert del giorno")
        
        # Join all lines to create the formatted menu
        formatted_menu = "\n".join(result_lines)
        
        return formatted_menu
    
    def _get_section_emoji(self, section: str) -> str:
        """Get an appropriate emoji for a menu section"""
        emojis = {
            "primi": "🍝",
            "secondi": "🍗",
            "contorni": "🥗",
            "dessert": "🍰"
        }
        return emojis.get(section, "🍽️")
        
    def _generate_placeholder_menu(self, cafeteria, meal_type="pranzo"):
        """Generate a placeholder menu for a specific cafeteria and meal type"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.logger.debug(f"Generated {meal_type} placeholder menu for {cafeteria} on {today}")
        
        meal_display = "PRANZO" if meal_type == "pranzo" else "CENA"
        
        # Different menu items for different cafeterias and meal types
        menu_items = {
            "Principe Amedeo": {
                "pranzo": [
                    "Pasta al pomodoro/Minestra di verdure",
                    "Petto di pollo/Frittata alle verdure",
                    "Insalata mista/Patate al forno",
                ],
                "cena": [
                    "Risotto ai funghi/Pasta all'arrabbiata",
                    "Filetto di merluzzo/Formaggio",
                    "Verdure grigliate/Insalata",
                ]
            },
            "Castelfidardo": {
                "pranzo": [
                    "Risotto con funghi/Pasta al pesto",
                    "Pollo arrosto/Frittata di verdure",
                    "Insalata verde/Patate arrosto",
                ],
                "cena": [
                    "Pasta alla carbonara/Zuppa di verdure",
                    "Pesce grigliato/Pollo alla griglia",
                    "Verdure al vapore/Insalata mista",
                ]
            },
            "Paolo Borsellino": {
                "pranzo": [
                    "Lasagna al forno/Minestrone",
                    "Tacchino arrosto/Polpette di carne",
                    "Spinaci saltati/Patate fritte",
                ],
                "cena": [
                    "Pasta al ragù/Risotto alla milanese",
                    "Bistecca di manzo/Formaggio misto",
                    "Verdure grigliate/Insalata di pomodori",
                ]
            },
            "Perrone": {
                "pranzo": [
                    "Penne al sugo/Riso con verdure",
                    "Spezzatino di manzo/Frittata di patate",
                    "Insalata mista/Carote al vapore",
                ],
                "cena": [
                    "Pasta al pesto/Zuppa di legumi",
                    "Pollo alla griglia/Filetto di pesce",
                    "Verdure al forno/Insalata verde",
                ]
            }
        }
        
        # Get menu items based on cafeteria and meal type, or use defaults
        items = menu_items.get(cafeteria, {}).get(meal_type, [
            f"Primo piatto ({meal_display})",
            f"Secondo piatto ({meal_display})",
            f"Contorno ({meal_display})"
        ])
        
        placeholder = f"🍽️ *MENSA {cafeteria.upper()}* 🍽️\n"
        placeholder += f"*Menù {meal_type.capitalize()} - {today}*\n\n"
        
        for i, item in enumerate(items):
            placeholder += f"• {item}\n"
        
        placeholder += "• Frutta fresca/Dessert del giorno"
        
        return placeholder
    
    def get_menu(self, cafeteria_name: str, meal_type: str = "pranzo") -> str:
        """
        Get menu for a specific cafeteria and meal type
        """
        # Map old name to new name if needed (for backward compatibility)
        if cafeteria_name in self.name_mapping:
            mapped_name = self.name_mapping[cafeteria_name]
            self.logger.debug(f"Mapping old cafeteria name '{cafeteria_name}' to '{mapped_name}'")
            cafeteria_name = mapped_name
            
        # Get menu from app cache specifying meal type
        return self.app.get_menu(cafeteria_name, meal_type)

