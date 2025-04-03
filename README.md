# PolitoMensa Bot

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

- **Tutti i menù** - View menus for all cafeterias
- **Central** - View menu for Central cafeteria
- **Castelfidardo** - View menu for Castelfidardo cafeteria
- **Sobrero** - View menu for Sobrero cafeteria
- **Corso Duca** - View menu for Corso Duca cafeteria
- **Aggiorna menù** - Force update of today's menus
- **Aiuto** - Show help information

## Troubleshooting

### OCR Issues

If you experience OCR issues:

1. Verify Tesseract is correctly installed: run `tesseract --version` in your terminal
2. Ensure the Italian language pack is installed
3. Check the logs for specific errors

### Instagram API Issues

If you see JSONDecodeError messages in the logs:

1. This is often due to Instagram's rate limiting or API changes
2. The application will attempt to use alternative methods to fetch stories
3. If problems persist, try again later or consider refreshing your Instagram session:
   ```
   python -c "from src.credentials import set_instagram_credentials; set_instagram_credentials()"
   ```

### Bot Connection Issues

1. Verify your Telegram token is correct
2. Ensure your internet connection is working
3. Check the logs for API errors

## License

MIT
