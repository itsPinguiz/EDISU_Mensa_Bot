import os
import re
from typing import Dict, List, Optional
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from src.logger import get_logger
import platform
import sys

logger = get_logger("ocr")

# Configure Tesseract path for Windows
def configure_tesseract():
    """Configure the Tesseract executable path based on operating system with enhanced detection"""
    if platform.system() == "Windows":
        # Expanded list of common installation paths on Windows
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            # Add UB Mannheim default path which is commonly used
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            # Add user profile paths (common location when installed by user)
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
            os.path.join(os.environ.get('APPDATA', ''), 'Tesseract-OCR', 'tesseract.exe'),
            # Python environment paths
            os.path.join(sys.prefix, 'Tesseract-OCR', 'tesseract.exe')
        ]
        
        # Check if any of these paths exist
        for path in possible_paths:
            if os.path.isfile(path):
                logger.info(f"Setting Tesseract path to: {path}")
                pytesseract.pytesseract.tesseract_cmd = path
                return True
        
        # If not found in common locations, try to find in PATH
        try:
            import subprocess
            output = subprocess.check_output(['where', 'tesseract'], shell=True).decode().strip()
            if output and os.path.isfile(output.splitlines()[0]):
                path = output.splitlines()[0]
                logger.info(f"Found Tesseract in PATH: {path}")
                pytesseract.pytesseract.tesseract_cmd = path
                return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        logger.warning("Could not find Tesseract executable in common locations or PATH")
        return False
    else:
        # On Linux/Mac, also verify it's actually installed
        try:
            import subprocess
            output = subprocess.check_output(['which', 'tesseract']).decode().strip()
            if output:
                logger.info(f"Found Tesseract in PATH: {output}")
                return True
            return False
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("Tesseract not found in PATH on Linux/Mac")
            return False

# Try to configure Tesseract path on module import
configure_tesseract()

def preprocess_image(image: Image.Image) -> Image.Image:
    """Enhanced preprocessing for better OCR results"""
    logger.debug("Preprocessing image for OCR")
    
    # Convert to grayscale
    image = image.convert('L')
    
    # Resize for optimal OCR (better results around 300 DPI)
    scale_factor = 2  # Scale up for better detail
    width, height = image.size
    new_width = width * scale_factor
    new_height = height * scale_factor
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Convert to numpy array for OpenCV operations
    img_array = np.array(image)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Noise reduction
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
    
    # Dilation to make text more prominent
    kernel = np.ones((1,1), np.uint8)
    dilated = cv2.dilate(denoised, kernel, iterations=1)
    
    # Convert back to PIL Image
    processed_image = Image.fromarray(dilated)
    
    return processed_image

def extract_text_from_image(image_path: str, lang: str = 'ita') -> str:
    """
    Extract text from an image using OCR
    
    Args:
        image_path: Path to the image file
        lang: Language code for OCR (default: Italian)
        
    Returns:
        Extracted text
    """
    logger.debug(f"Extracting text from image: {image_path}")
    
    # Check if the image exists
    if not os.path.isfile(image_path):
        logger.error(f"Image file not found: {image_path}")
        return ""
    
    try:
        # Open the image
        image = Image.open(image_path)
        
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Extract text using Tesseract
        custom_config = r'--psm 6'  # Assume a single block of text
        text = pytesseract.image_to_string(processed_image, lang=lang, config=custom_config)
        
        logger.debug(f"Extracted {len(text)} characters from image")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from image: {str(e)}", exc_info=True)
        return ""

def extract_text_from_image_directly(image: Image.Image, lang: str = 'ita') -> str:
    """Extract text with improved OCR configuration"""
    logger.debug(f"Extracting text with enhanced OCR settings")
    
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Configure Tesseract for better menu text recognition
        custom_config = (
            f'--psm 6 '  # Assume uniform text block
            f'--oem 3 '  # Use LSTM OCR Engine
            f'-c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,/()- " '
            f'-c preserve_interword_spaces=1 '
            f'-c textord_heavy_nr=1 '
        )
        
        # Extract text
        text = pytesseract.image_to_string(processed_image, lang=lang, config=custom_config)
        
        # Post-processing
        text = text.replace('|', 'I')
        text = text.replace('[', '(').replace(']', ')')
        text = text.replace('{', '(').replace('}', ')')
        text = text.replace('°', 'o').replace('º', 'o')
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        
        logger.debug(f"Extracted {len(text)} characters from image")
        return text
        
    except Exception as e:
        logger.error(f"Error extracting text from image: {str(e)}", exc_info=True)
        return ""

def identify_menu_sections(text: str) -> Dict[str, str]:
    """
    Identify menu sections (primo, secondo, etc.) in extracted text
    
    Args:
        text: OCR extracted text
        
    Returns:
        Dictionary of menu sections
    """
    logger.debug("Identifying menu sections")
    
    # Define section keywords
    section_patterns = {
        "primo": [r"prim[oi]", r"pasta", r"risotto", r"zupp[ae]"],
        "secondo": [r"second[oi]", r"carne", r"pesce"],
        "contorno": [r"contorn[oi]", r"verdur[ae]", r"insalat[ae]"],
        "dessert": [r"dessert", r"dolc[ei]", r"frutt[ao]"]
    }
    
    # Split text into lines and clean them
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Initialize sections
    sections = {k: [] for k in section_patterns.keys()}
    current_section = None
    
    # Process lines
    for line in lines:
        line_lower = line.lower()
        
        # Check if this line starts a new section
        for section, patterns in section_patterns.items():
            if any(re.search(pattern, line_lower) for pattern in patterns):
                current_section = section
                break
        
        # Add line to current section
        if current_section:
            sections[current_section].append(line)
    
    # Convert lists to strings
    sections = {k: '\n'.join(v) for k, v in sections.items() if v}
    
    logger.debug(f"Identified {len(sections)} menu sections")
    return sections
