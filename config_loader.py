import json
import os
from pathlib import Path
from PyQt6.QtGui import QGuiApplication # type: ignore

# Global variable to store config
CONFIG_FILE = "config.json"
CONFIG = {}

def load_config():
    global CONFIG
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found.")
    
    with open(CONFIG_FILE, "r") as file:
        CONFIG = json.load(file)

# Load config once at startup
load_config()

# Define global variables
DEBUG = CONFIG.get("debug", "NO").strip().upper() == "YES"
MYSQL_CONFIG = CONFIG.get("mysql", {})
KEA_SERVER = f"{CONFIG['server_address']}:{CONFIG['server_port']}"
WINDOW_SIZES = CONFIG.get("WINDOW_SIZES", {})
SPLITTER_SIZES = CONFIG.get("SPLITTER_SIZES", {})

# Check if screen resolution should be used
USE_SCREEN_RESOLUTION = WINDOW_SIZES.get("use_screen_resolution", False)

def debug_print(message):
    """Prints debug messages if debugging is enabled."""
    if DEBUG:
        print(f"[DEBUG] {message}")

def get_screen_size():
    """Returns the screen width and height (80% of the available screen)."""
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])  # Create a temporary instance if needed
    
    screen = app.primaryScreen()
    if screen is None:
        debug_print("Screen detection failed. Using default window size (1000x600).")
        return 1000, 600  # Safe fallback

    geometry = screen.geometry()
    screen_width = int(geometry.width() * 0.8)  # 80% width
    screen_height = int(geometry.height() * 0.8)  # 80% height
    
    debug_print(f"Detected screen size: {geometry.width()}x{geometry.height()}, using 80% -> {screen_width}x{screen_height}.")
    return screen_width, screen_height

def apply_dynamic_window_sizes():
    """Updates window sizes if 'use_screen_resolution' is enabled."""
    if USE_SCREEN_RESOLUTION:
        screen_width, screen_height = get_screen_size()
        
        # Override main window size
        if "main_window" in WINDOW_SIZES:
            WINDOW_SIZES["main_window"]["width"] = screen_width
            WINDOW_SIZES["main_window"]["height"] = screen_height
            debug_print(f"Using detected resolution for main window: {screen_width}x{screen_height}")

        # Override leases dialog size
        if "leases_dialog" in WINDOW_SIZES:
            WINDOW_SIZES["leases_dialog"]["width"] = screen_width
            WINDOW_SIZES["leases_dialog"]["height"] = screen_height
            debug_print(f"Using detected resolution for leases dialog: {screen_width}x{screen_height}")

    else:
        # Using predefined resolution from config.json
        mw = WINDOW_SIZES.get("main_window", {})
        ld = WINDOW_SIZES.get("leases_dialog", {})
        debug_print(f"Using resolution from config.json: Main Window {mw.get('width', 'N/A')}x{mw.get('height', 'N/A')}, "
                    f"Leases Dialog {ld.get('width', 'N/A')}x{ld.get('height', 'N/A')}.")