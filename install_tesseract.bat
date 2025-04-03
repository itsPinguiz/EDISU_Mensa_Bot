@echo off
echo PolitoMensa - Tesseract OCR Installer Helper
echo ==========================================
echo.
echo This script will help you download and install Tesseract OCR for Windows.
echo Tesseract is required for extracting menu text from Instagram stories.
echo.
echo Without Tesseract, the application will still work but will use placeholder
echo menus instead of the actual menus from Instagram.
echo.
echo Press any key to open the Tesseract download page...
pause > nul

start https://github.com/UB-Mannheim/tesseract/wiki

echo.
echo Download and install the latest version (64-bit is recommended).
echo.
echo IMPORTANT: During installation, make sure to:
echo 1. Check "Add to PATH" option
echo 2. Install the Italian language data
echo.
echo Default installation paths (for reference):
echo - C:\Program Files\Tesseract-OCR\tesseract.exe
echo - C:\Program Files (x86)\Tesseract-OCR\tesseract.exe
echo.
echo After installation, you will need to restart your command prompt 
echo or PowerShell before running the bot.
echo.
echo To verify Tesseract is installed correctly, open a new command prompt 
echo and run: tesseract --version
echo.
echo Press any key to exit...
pause > nul
