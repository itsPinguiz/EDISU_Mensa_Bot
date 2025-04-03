# EDISU Mensa Bot

A Telegram bot that extracts cafeteria menus from Instagram stories and makes them available via an interactive button interface.

## ⚠️ Important: Tesseract OCR Required

This application requires Tesseract OCR to extract menu text from Instagram stories. Without Tesseract, the bot will still work but will show placeholder menus instead of actual menus.

**On Windows**: Run `install_tesseract.bat` included in this repository for easy installation.

## Installation

### Prerequisites

1. **Python 3.9+**
2. **Tesseract OCR**:
   - **Windows**: Download and install from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
     - **Important**: Check the "Add to PATH" option during installation
     - Also select the Italian language pack during installation
   - **macOS**: `brew install tesseract tesseract-lang`
   - **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr tesseract-ocr-ita`

3. **After installing Tesseract**: Restart your terminal/command prompt before running the bot

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/PolitoMensa.git
   cd PolitoMensa
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up credentials:
   ```
   python setup_credentials.py
   ```
   
   This will prompt you to enter your Telegram bot token and Instagram credentials.

## Usage

1. Start the bot:
   ```
   python -m src.app
   ```

2. In Telegram, find your bot and send the `/start` command.

3. Use the interactive buttons to navigate the bot's features.

## Interface Features

The bot uses an interactive button-based interface with the following options:

- **Menù Pranzo** - View lunch menus for available cafeterias
- **Menù Cena** - View dinner menus for available cafeterias
- **Aggiorna menù** - Force update of today's menus
- **Aiuto** - Show help information
