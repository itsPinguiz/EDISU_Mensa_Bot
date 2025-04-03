import os
import re
from typing import Dict, List, Optional
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from src.logger import get_logger
import platform

logger = get_logger("ocr")

# Configure Tesseract path for Windows
def configure_tesseract():
    """Configure the Tesseract executable path based on operating system"""
    if platform.system() == "Windows":
        # Common installation paths on Windows
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            # Add UB Mannheim default path which is commonly used
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        ]
        
        # Check if any of these paths exist
        for path in possible_paths:
            if os.path.isfile(path):
                logger.info(f"Setting Tesseract path to: {path}")
                pytesseract.pytesseract.tesseract_cmd = path
                return True
        
        logger.warning("Could not find Tesseract executable in common locations")
        return False
    else:
        # Check for PythonAnywhere environment
        if "PYTHONANYWHERE_SITE" in os.environ:
            pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
            logger.info("PythonAnywhere environment detected, using system Tesseract")
        else:
            # On Linux/Mac, pytesseract should find it if it's in PATH
            logger.debug("Non-Windows OS detected, relying on system PATH for Tesseract")
        return True

# Try to configure Tesseract path on module import
configure_tesseract()

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess an image to improve OCR results
    
    Args:
        image: PIL Image object
        
    Returns:
        PIL Image object optimized for OCR
    """
    logger.debug("Preprocessing image for OCR")
    
    # Convert to grayscale
    image = image.convert('L')
    
    # Resize if image is too large (helps OCR accuracy)
    width, height = image.size
    max_dimension = 1800
    if width > max_dimension or height > max_dimension:
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        image = image.resize((new_width, new_height), Image.LANCZOS)
        logger.debug(f"Resized image to {new_width}x{new_height}")
    
    # Increase contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # Apply sharpening filter
    image = image.filter(ImageFilter.SHARPEN)
    
    # Apply thresholding using OpenCV for better results
    img_array = np.array(image)
    _, thresh = cv2.threshold(img_array, 150, 255, cv2.THRESH_BINARY)
    
    # Additional denoising for cleaner text
    denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
    
    # Convert back to PIL Image
    processed_image = Image.fromarray(denoised)
    
    logger.debug("Image preprocessing complete")
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
    """
    Extract text directly from a PIL Image object using OCR
    
    Args:
        image: PIL Image object
        lang: Language code for OCR (default: Italian)
        
    Returns:
        Extracted text
    """
    logger.debug(f"Extracting text from image using lang={lang}")
    
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Extract text using Tesseract
        # Use a configuration optimized for menu text
        custom_config = r'--psm 6 --oem 3'  # Assume a uniform text block with OCR engine mode 3
        text = pytesseract.image_to_string(processed_image, lang=lang, config=custom_config)
        
        logger.debug(f"Extracted {len(text)} characters from image")
        
        # Basic post-processing
        # Replace common OCR errors
        text = text.replace('|', 'I').replace('[', '(').replace(']', ')')
        
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
