from instagrapi import Client
from typing import Dict, List, Optional, Tuple
import os
import re
import logging
import tempfile
from datetime import datetime, timedelta
import pytesseract
from PIL import Image
import io
import requests
import time
import json
from src.logger import get_logger
from src.credentials import get_instagram_credentials

class InstApi:
    def __init__(self, app):
        self.app = app
        self.logger = get_logger()
        self.logger.info("Initializing Instagram API client")
        self.client = Client()
        self.logged_in = False
        self.demo_mode = False  # Add demo mode flag
        
        # Track login attempts and implement exponential backoff
        self.login_attempts = 0
        self.login_backoff = 5  # Initial backoff in seconds
        self.max_login_attempts = 3
        
        # Store session cookies to avoid frequent logins
        self.session_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "data", 
            "instagram_session.json"
        )
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
        
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
        
        # Add retry configuration for API requests
        self.max_retries = 3
        self.retry_delay = 2  # Initial delay in seconds
        
        # Add caching for OCR results to avoid redundant processing
        self.ocr_cache = {}
        self.cache_expiry = 3600  # Cache OCR results for 1 hour
        
        self.logger.debug(f"Configured to fetch menus for {len(self.cafeterias)} cafeterias from account: {self.cafeteria_account}")
        
    def login(self):
        """Login to Instagram using secure credentials with enhanced error handling"""
        if self.demo_mode:
            self.logger.info("Demo mode enabled - skipping Instagram login")
            return False
            
        self.logger.info("Logging in to Instagram")
        
        # Check if we've exceeded max login attempts
        if self.login_attempts >= self.max_login_attempts:
            self.logger.warning(f"Exceeded maximum login attempts ({self.max_login_attempts})")
            return False
        
        # Increment login attempt counter
        self.login_attempts += 1
        
        # Apply exponential backoff if this is a retry
        if self.login_attempts > 1:
            backoff_time = self.login_backoff * (2 ** (self.login_attempts - 2))
            self.logger.info(f"Login attempt {self.login_attempts} - waiting {backoff_time} seconds")
            time.sleep(backoff_time)
        
        try:
            # First try to load session from file
            if os.path.exists(self.session_file):
                self.logger.debug("Attempting to use saved session")
                try:
                    self.client.load_settings(self.session_file)
                    # Verify session is valid with a simple request that doesn't count against rate limits
                    user_id = self.client.user_id
                    if user_id:
                        self.logger.info("Successfully reused Instagram session")
                        self.logged_in = True
                        return True
                except Exception as e:
                    self.logger.warning(f"Failed to reuse session: {str(e)}")
                    # Continue to regular login if session reuse failed
            
            # Get credentials from secure storage
            try:
                username, password = get_instagram_credentials()
                self.logger.debug(f"Attempting login with username: {username}")
            except Exception as e:
                self.logger.error(f"Failed to get credentials: {str(e)}")
                return False
            
            # Attempt login with proper error handling
            try:
                self.client.login(username, password)
                # Save session for future reuse
                self.client.dump_settings(self.session_file)
                self.logged_in = True
                self.logger.info("Successfully logged in to Instagram")
                return True
            except Exception as e:
                error_msg = str(e)
                if "challenge_required" in error_msg.lower():
                    self.logger.error("Instagram requires verification - please log in manually in a browser first")
                elif "ip address" in error_msg.lower():
                    self.logger.error(f"Instagram login failed: IP address may be blocked. {error_msg}")
                elif "password" in error_msg.lower():
                    self.logger.error("Instagram login failed: Incorrect password")
                elif "throttled" in error_msg.lower() or "rate limit" in error_msg.lower():
                    self.logger.error(f"Instagram login throttled/rate limited: {error_msg}")
                else:
                    self.logger.error(f"Instagram login failed: {error_msg}", exc_info=True)
                return False
                
        except Exception as e:
            self.logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
            return False
    
    def fetch_menus(self) -> Dict[str, Dict[str, str]]:
        """Fetch menus from Instagram stories with improved fallback mechanism"""
        self.logger.info("Fetching menus from Instagram stories")
        
        # Initialize with empty menus
        menus = {}
        for cafeteria in self.cafeterias:
            menus[cafeteria] = {
                "pranzo": "Menu pranzo not available",
                "cena": "Menu cena not available"
            }
        
        # If in demo mode, just return placeholder menus
        if self.demo_mode:
            self.logger.info("Demo mode enabled - generating placeholder menus")
            for cafeteria in self.cafeterias:
                menus[cafeteria]["pranzo"] = self._generate_placeholder_menu(cafeteria, "pranzo")
                menus[cafeteria]["cena"] = self._generate_placeholder_menu(cafeteria, "cena")
            return menus
        
        # If not logged in, try to login first
        if not self.logged_in:
            self.logger.warning("Not logged in to Instagram, attempting login")
            login_success = self.login()
            if not login_success:
                self.logger.error("Login failed, cannot fetch menus")
                # Return placeholder menus
                for cafeteria in self.cafeterias:
                    menus[cafeteria]["pranzo"] = self._generate_placeholder_menu(cafeteria, "pranzo", "Instagram login failed. Using placeholder menu.")
                    menus[cafeteria]["cena"] = self._generate_placeholder_menu(cafeteria, "cena", "Instagram login failed. Using placeholder menu.")
                return menus
        
        # Rest of the existing fetch_menus implementation
        try:
            from instagrapi.mixins.public import PublicRequestMixin
            original_public_request = PublicRequestMixin.public_request
            
            def patched_public_request(self, *args, **kwargs):
                try:
                    return original_public_request(self, *args, **kwargs)
                except json.JSONDecodeError as e:
                    get_logger().debug(f"Suppressed JSONDecodeError in public_request: {str(e)}")
                    return {}
                    
            PublicRequestMixin.public_request = patched_public_request
        except:
            self.logger.debug("Could not apply JSONDecodeError patch")
        
        try:
            user_id = self._get_user_id_with_retry(self.cafeteria_account)
            if not user_id:
                self.logger.error(f"Could not get user ID for {self.cafeteria_account}")
                return menus
                
            self.logger.debug(f"Found user ID for {self.cafeteria_account}: {user_id}")
            
            stories = self._get_stories_with_retry(user_id)
            
            if stories:
                self.logger.info(f"Found {len(stories)} stories")
                
                tesseract_available = self._check_tesseract()
                
                if tesseract_available:
                    extracted_menus = self._extract_menus_from_stories(stories)
                    
                    for cafeteria, menu_data in extracted_menus.items():
                        if cafeteria in menus:
                            menus[cafeteria] = menu_data
                            self.logger.debug(f"Updated menus for {cafeteria}")
                    
                    missing_cafeterias = []
                    for cafe in self.cafeterias:
                        if menus[cafe]["pranzo"] == "Menu pranzo not available" and menus[cafe]["cena"] == "Menu cena not available":
                            missing_cafeterias.append(cafe)
                    
                    if missing_cafeterias:
                        self.logger.warning(f"Could not find menus for: {', '.join(missing_cafeterias)}")
                        for cafeteria in missing_cafeterias:
                            menus[cafeteria]["pranzo"] = self._generate_placeholder_menu(cafeteria, "pranzo")
                            menus[cafeteria]["cena"] = self._generate_placeholder_menu(cafeteria, "cena")
                            self.logger.info(f"Generated placeholder menus for {cafeteria}")
                else:
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
        
        try:
            PublicRequestMixin.public_request = original_public_request
        except:
            pass
            
        return menus
    
    def _get_user_id_with_retry(self, username: str) -> Optional[str]:
        user_id = None
        
        if hasattr(self, '_cached_user_id') and self._cached_user_id:
            self.logger.debug(f"Using cached user ID: {self._cached_user_id}")
            return self._cached_user_id
            
        for attempt in range(1, self.max_retries + 1):
            try:
                user_id = self.client.user_id_from_username(username)
                if user_id:
                    self._cached_user_id = user_id
                    return user_id
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSONDecodeError on attempt {attempt}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    if username == "edisu_piemonte":
                        self.logger.warning("Using hardcoded user ID for edisu_piemonte as fallback")
                        user_id = "44062439959"
                        self._cached_user_id = user_id
                        return user_id
                    self.logger.error(f"Failed to get user ID after {self.max_retries} attempts")
            except Exception as e:
                self.logger.error(f"Error getting user ID: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    time.sleep(delay)
                    
        if hasattr(self, '_cached_user_id') and self._cached_user_id:
            return self._cached_user_id
            
        return None
    
    def _get_stories_with_retry(self, user_id: str) -> List:
        for attempt in range(1, self.max_retries + 1):
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, 
                                          message=".*JSONDecodeError in public_request.*")
                    stories = self.client.user_stories(user_id)
                    self.logger.info(f"Found {len(stories)} stories")
                    return stories
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSONDecodeError on attempt {attempt}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    try:
                        self.logger.warning("Trying direct API call for stories as fallback")
                        response = self.client.private.get(f"feed/user/{user_id}/story/")
                        if response.get("reel"):
                            items = response.get("reel", {}).get("items", [])
                            self.logger.info(f"Found {len(items)} stories via direct API call")
                            processed_stories = []
                            for item in items:
                                story = type('Story', (), {
                                    'id': item.get('id'),
                                    'pk': item.get('pk'),
                                    'thumbnail_url': item.get('image_versions2', {}).get('candidates', [{}])[0].get('url')
                                })
                                processed_stories.append(story)
                            return processed_stories
                    except Exception as e:
                        self.logger.error(f"Error in direct API fallback: {str(e)}")
                    
                    self.logger.warning(f"Failed to get stories after {self.max_retries} attempts, proceeding with empty list")
                    return []
            except Exception as e:
                self.logger.error(f"Error getting stories: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                
        return []
    
    def _check_tesseract(self) -> bool:
        try:
            from src.ocr_utils import configure_tesseract
            configure_tesseract()
            
            import pytesseract
            pytesseract.get_tesseract_version()
            self.logger.debug("Tesseract OCR is available")
            return True
        except Exception as e:
            self.logger.warning(f"Tesseract OCR is not available: {str(e)}")
            return False
    
    def _extract_menus_from_stories(self, stories) -> Dict[str, Dict[str, str]]:
        self.logger.debug(f"Extracting menus from {len(stories)} stories")
        extracted_menus = {}
        
        for cafeteria in self.cafeterias:
            extracted_menus[cafeteria] = {
                "pranzo": "",
                "cena": ""
            }
        
        current_stories = self._filter_current_day_stories(stories)
        if len(current_stories) < len(stories):
            self.logger.info(f"Filtered out {len(stories) - len(current_stories)} older stories, processing {len(current_stories)} current day stories")
        
        story_texts = []
        for i, story in enumerate(current_stories):
            story_id = getattr(story, 'id', f'story_{i}')
            self.logger.debug(f"Processing story {story_id}")
            
            ocr_text = self._extract_text_from_story(story)
            if not ocr_text:
                self.logger.warning(f"Could not extract text from story {story_id}")
                continue
            
            story_texts.append((story_id, ocr_text))
        
        for story_id, ocr_text in story_texts:
            cafeteria = self._identify_cafeteria_from_text(ocr_text, extracted_menus)
            if not cafeteria:
                self.logger.debug(f"Could not identify cafeteria for story {story_id}")
                continue
                
            meal_type = self._identify_meal_type(ocr_text)
            
            menu_text = self._process_menu_text(ocr_text, cafeteria, meal_type)
            
            if extracted_menus[cafeteria][meal_type]:
                self.logger.debug(f"Already have a {meal_type} menu for {cafeteria}, checking quality")
                if len(menu_text) > len(extracted_menus[cafeteria][meal_type]):
                    extracted_menus[cafeteria][meal_type] = menu_text
                    self.logger.info(f"Updated {meal_type} menu for {cafeteria} from story {story_id}")
            else:
                extracted_menus[cafeteria][meal_type] = menu_text
                self.logger.info(f"Extracted {meal_type} menu for {cafeteria} from story {story_id}")
        
        return extracted_menus

    def _filter_current_day_stories(self, stories: List) -> List:
        from datetime import datetime, timedelta
        import re
        
        current_date = datetime.now().date()
        yesterday = current_date - timedelta(days=1)
        
        today_str_formats = [
            current_date.strftime("%d/%m/%Y"),
            current_date.strftime("%d-%m-%Y"),
            current_date.strftime("%d.%m.%Y"),
            current_date.strftime("%d %B %Y"),
            current_date.strftime("%d %b %Y"),
            current_date.strftime("%d/%m"),
            current_date.strftime("%d-%m"),
            current_date.strftime("%d.%m")
        ]
        italian_months = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                         "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
        month_number = current_date.month
        today_str_formats.append(f"{current_date.day} {italian_months[month_number-1]} {current_date.year}")
        today_str_formats.append(f"{current_date.day} {italian_months[month_number-1][:3]} {current_date.year}")
        today_str_formats.append(f"{current_date.day} {italian_months[month_number-1]}")
        
        date_patterns = [
            r'\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b',
            r'\b\d{1,2}[/.\-]\d{1,2}\b',
            r'\b\d{1,2}\s+[a-zA-Z]+\s+\d{2,4}\b',
            r'\b\d{1,2}\s+[a-zA-Z]+\b'
        ]
        
        current_day_stories = []
        
        for story in stories:
            story_date = None
            
            if hasattr(story, 'taken_at'):
                story_date = story.taken_at.date() if hasattr(story.taken_at, 'date') else None
            elif hasattr(story, 'created_time'):
                story_date = datetime.fromtimestamp(story.created_time).date()
            elif hasattr(story, 'imported_taken_at'):
                story_date = datetime.fromtimestamp(story.imported_taken_at).date() 
            elif hasattr(story, 'pk'):
                try:
                    pk_parts = str(story.pk).split('_')
                    if len(pk_parts) > 1 and pk_parts[0].isdigit() and len(pk_parts[0]) > 8:
                        timestamp = int(pk_parts[0]) / 1000
                        story_date = datetime.fromtimestamp(timestamp).date()
                except (ValueError, TypeError, IndexError):
                    pass
            
            if story_date is None:
                self.logger.warning(f"Could not determine date for story {getattr(story, 'id', 'unknown')}, including it by default")
                current_day_stories.append(story)
                continue
                
            if story_date == current_date:
                current_day_stories.append(story)
                continue
                
            if story_date == yesterday:
                preview_text = self._extract_text_from_story(story)
                
                menu_indicators = ["menù", "menu", "primo", "pranzo", "cena", "mensa"]
                has_menu = preview_text and any(indicator in preview_text.lower() for indicator in menu_indicators)
                
                if has_menu:
                    has_today_date = False
                    
                    for date_format in today_str_formats:
                        if date_format.lower() in preview_text.lower():
                            self.logger.info(f"Including yesterday's story because it contains today's date: {date_format}")
                            has_today_date = True
                            break
                    
                    if not has_today_date:
                        all_dates = []
                        for pattern in date_patterns:
                            matches = re.findall(pattern, preview_text)
                            all_dates.extend(matches)
                        
                        if all_dates:
                            self.logger.debug(f"Found dates in story: {all_dates}")
                            
                            for date_str in all_dates:
                                date_parts = re.split(r'[/\-\.\s]+', date_str)
                                
                                if len(date_parts) >= 2 and date_parts[0].isdigit():
                                    day_part = int(date_parts[0])
                                    if day_part == current_date.day:
                                        if len(date_parts) >= 2:
                                            if date_parts[1].isdigit() and int(date_parts[1]) == current_date.month:
                                                has_today_date = True
                                                break
                                            elif not date_parts[1].isdigit():
                                                month_part = date_parts[1].lower()
                                                for i, month in enumerate(italian_months, 1):
                                                    if month_part in month.lower() and i == current_date.month:
                                                        has_today_date = True
                                                        break
                    
                    if has_today_date:
                        self.logger.info(f"Including yesterday's story as it contains today's date")
                        current_day_stories.append(story)
                    else:
                        self.logger.debug(f"Excluding yesterday's story as it doesn't contain today's date")
                else:
                    self.logger.debug(f"Excluding yesterday's story as it doesn't appear to be a menu")
            else:
                self.logger.debug(f"Excluding story from {story_date} as it's not from today or yesterday")
        
        self.logger.info(f"Filtered stories: keeping {len(current_day_stories)} out of {len(stories)} stories")
        return current_day_stories
    
    def _identify_meal_type(self, text: str) -> str:
        text_lower = text.lower()
        
        for meal_type, keywords in self.meal_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    self.logger.debug(f"Identified meal type as {meal_type}")
                    return meal_type
        
        return "pranzo"
    
    def _extract_text_from_story(self, story) -> str:
        if not self._check_tesseract():
            return ""
        
        try:
            story_id = getattr(story, 'id', '') or getattr(story, 'pk', '')
            
            cache_key = f"story_{story_id}"
            if cache_key in self.ocr_cache:
                cache_entry = self.ocr_cache[cache_key]
                cache_time, cached_text = cache_entry
                
                if time.time() - cache_time < self.cache_expiry:
                    self.logger.debug(f"Using cached OCR result for story {story_id}")
                    return cached_text
            
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
            
            self.logger.debug("Running OCR on story image")
            text = pytesseract.image_to_string(image, lang='ita')
            self.logger.debug(f"OCR extracted {len(text)} characters")
            
            self.ocr_cache[cache_key] = (time.time(), text)
            
            if len(self.ocr_cache) > 100:
                current_time = time.time()
                self.ocr_cache = {k: v for k, v in self.ocr_cache.items() 
                                 if current_time - v[0] < self.cache_expiry}
            
            return text
        except Exception as e:
            self.logger.error(f"Error extracting text from story: {str(e)}", exc_info=True)
            return ""
    
    def _identify_cafeteria_from_text(self, text: str, existing_menus: Dict[str, Dict[str, str]] = None) -> Optional[str]:
        if not text:
            return None
            
        if existing_menus is None:
            existing_menus = {}
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text_lower = text.lower()
        
        for i, line in enumerate(lines[:3]):
            line_lower = line.lower()
            if "mensa" in line_lower:
                self.logger.debug(f"Found 'Mensa' reference in line: {line}")
                for cafeteria, keywords in self.cafeteria_keywords.items():
                    for keyword in keywords:
                        if keyword in line_lower:
                            self.logger.info(f"Identified cafeteria {cafeteria} from line: {line}")
                            return cafeteria
        
        for cafeteria, keywords in self.cafeteria_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    self.logger.debug(f"Identified cafeteria {cafeteria} from keyword '{keyword}'")
                    return cafeteria
        
        self.logger.warning("Could not identify cafeteria from keywords, attempting content analysis")
        
        menu_indicators = ["primi piatti", "secondi piatti", "contorni", "menù", "pranzo", "cena"]
        if any(indicator in text_lower for indicator in menu_indicators):
            for cafeteria in self.cafeterias:
                if cafeteria not in existing_menus:
                    self.logger.debug(f"Assigning menu to {cafeteria} based on menu indicators")
                    return cafeteria
        
        return None
    
    def _process_menu_text(self, text: str, cafeteria: str, meal_type: str = "pranzo") -> str:
        self.logger.debug(f"Processing {meal_type} menu text for {cafeteria} ({len(text)} chars)")
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        from datetime import datetime
        today = datetime.now().strftime("%d/%m/%Y")
        
        result_lines = []
        result_lines.append(f"*{today}*")
        result_lines.append("")
        
        sections_data = {'primi': [], 'secondi': [], 'contorni': []}
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if any(keyword in line_lower for keyword in 
                  ["mensa", "menù", "menu", "data", "edisu", "piemonte"]):
                continue
            
            is_section_header = False
            new_section = None
            
            for section, headers in self.section_headers.items():
                if any(header in line_lower for header in headers):
                    new_section = section
                    is_section_header = True
                    break
            
            if is_section_header:
                current_section = new_section
            elif current_section and current_section in sections_data:
                if len(line) > 3:
                    sections_data[current_section].append(line)
        
        for section in self.section_order[:-1]:
            if section in sections_data and sections_data[section]:
                section_emoji = self._get_section_emoji(section)
                result_lines.append(f"{section_emoji} *{section.upper()}* {section_emoji}")
                
                for dish in sections_data[section]:
                    dish_text = dish.lower()
                    if dish_text:
                        dish_text = dish_text[0].upper() + dish_text[1:]
                    result_lines.append(f"• {dish_text}")
                
                result_lines.append("")
        
        dessert_emoji = self._get_section_emoji("dessert")
        result_lines.append(f"{dessert_emoji} *DESSERT* {dessert_emoji}")
        result_lines.append("• Frutta fresca")
        result_lines.append("• Dessert del giorno")
        
        formatted_menu = "\n".join(result_lines)
        
        return formatted_menu
    
    def _get_section_emoji(self, section: str) -> str:
        emojis = {
            "primi": "🍝",
            "secondi": "🍗",
            "contorni": "🥗",
            "dessert": "🍰"
        }
        return emojis.get(section, "🍽️")
        
    def _generate_placeholder_menu(self, cafeteria, meal_type="pranzo", reason=""):
        today = datetime.now().strftime("%Y-%m-%d")
        self.logger.debug(f"Generated {meal_type} placeholder menu for {cafeteria} on {today}")
        
        meal_display = "PRANZO" if meal_type == "pranzo" else "CENA"
        
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
        
        items = menu_items.get(cafeteria, {}).get(meal_type, [
            f"Primo piatto ({meal_display})",
            f"Secondo piatto ({meal_display})",
            f"Contorno ({meal_display})"
        ])
        
        placeholder = f"🍽️ *MENSA {cafeteria.upper()}* 🍽️\n"
        placeholder += f"*Menù {meal_type.capitalize()} - {today}*\n\n"
        
        if reason:
            placeholder += f"⚠️ {reason}\n\n"
        
        for i, item in enumerate(items):
            placeholder += f"• {item}\n"
        
        placeholder += "• Frutta fresca/Dessert del giorno"
        
        return placeholder
    
    def get_menu(self, cafeteria_name: str, meal_type: str = "pranzo") -> str:
        if cafeteria_name in self.name_mapping:
            mapped_name = self.name_mapping[cafeteria_name]
            self.logger.debug(f"Mapping old cafeteria name '{cafeteria_name}' to '{mapped_name}'")
            cafeteria_name = mapped_name
            
        return self.app.get_menu(cafeteria_name, meal_type)

