#!/usr/bin/env python3
"""
Script to securely store credentials for PolitoMensa bot
"""
from src.credentials import setup_credentials_interactively

if __name__ == "__main__":
    print("PolitoMensa Bot - Secure Credential Setup")
    print("=========================================")
    print("This script will store your credentials securely in your system's keyring.")
    print("You'll only need to run this once.\n")
    
    if setup_credentials_interactively():
        print("\nAll credentials stored successfully! You can now run the bot.")
    else:
        print("\nSome credentials could not be stored securely.")
        print("You may need to set them as environment variables instead.")
