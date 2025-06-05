#core/commands/bookmark_handers/jump_handler.py

import os
import subprocess
import platform
from colorama import Fore, Style
from core.tts import speak # Uses config internally

async def handle_jump_logic(parts: list, bookmark_storage, logger) -> bool:
    """
    Handles the 'zira bookmark jump <alias>' command logic.
    """
    if len(parts) < 4:
        await speak("Usage: zira bookmark jump <alias>")
        logger.warning("Bookmark jump command missing alias.")
        return True

    raw_alias = parts[3].strip()
    alias = raw_alias.strip("<>").strip()

    if not alias:
        await speak("Please provide a valid bookmark alias.")
        return True

    bookmarks = await bookmark_storage.load_bookmarks()
    
    if alias not in bookmarks:
        await speak(f"Bookmark '{alias}' not found.")
        logger.warning("Attempted to jump to non-existent bookmark: '%s'", alias)
        return True

    path = bookmarks[alias]
    await speak(f"Opening bookmark '{alias}'.")
    logger.info("Attempting to open path for alias '%s': %s", alias, path)
    print(Fore.MAGENTA + f"Attempting to open: {path}" + Style.RESET_ALL)

    # Re-expand in case environment or home changed since bookmark was saved
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)

    # Security: Check if path exists before attempting to open.
    if not os.path.exists(path):
        await speak(f"Error: Path '{path}' does not exist.")
        logger.error("Bookmark jump failed: Path '%s' does not exist.", path)
        return True

    try:
        system = platform.system()
        # Security: Use platform-specific, safe methods to open files/directories.
        # Avoids 'shell=True' in subprocess.run for security against command injection.
        if os.path.isdir(path):
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", path], check=False)
            else:  # Linux/Other
                subprocess.run(["xdg-open", path], check=False)
        elif os.path.isfile(path):
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        else:
            await speak(f"Error: Path '{path}' is not a file or directory.")
            logger.error("Bookmark jump failed: Path '%s' is not a valid file or directory type.", path)
            return True
    except FileNotFoundError:
        await speak("Error: Cannot open the file or folder on your system (no handler found).")
        logger.error("Bookmark jump failed: No OS handler for '%s'.", path)
    except Exception as e:
        await speak(f"Could not open path: {e}")
        logger.error("Error opening path '%s': %s", path, e, exc_info=True)

    return True
