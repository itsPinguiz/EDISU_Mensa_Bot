import requests
import base64
import os
import json
from PIL import Image
import io
from src.logger import get_logger

logger = get_logger("cloud_ocr")

# Use environment variable for API key
API_KEY = os.environ.get("OCR_API_KEY", "")

def extract_text_from_image_cloud(image):
    """
    Extract text from image using a cloud OCR service
    
    Args:
        image: PIL Image object
        
    Returns:
        Extracted text
    """
    logger.debug("Using cloud OCR service")
    
    # Convert image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    # Encode as base64
    encoded_image = base64.b64encode(img_byte_arr).decode('ascii')
    
    # Choose one of these services and implement
    # Example for OCR.space API
    try:
        url = 'https://api.ocr.space/parse/image'
        payload = {
            'apikey': API_KEY,
            'language': 'ita',
            'base64Image': 'data:image/png;base64,' + encoded_image,
            'isOverlayRequired': False
        }
        
        response = requests.post(url, data=payload)
        result = response.json()
        
        if result['IsErroredOnProcessing'] == False:
            extracted_text = result['ParsedResults'][0]['ParsedText']
            logger.debug(f"Cloud OCR extracted {len(extracted_text)} characters")
            return extracted_text
        else:
            logger.error(f"Cloud OCR error: {result['ErrorMessage']}")
            return ""
    except Exception as e:
        logger.error(f"Error calling cloud OCR service: {str(e)}")
        return ""
