#core/commands/bookmark_handers/add_handler.py

import os
import re
from colorama import Fore, Style
from core.tts import speak # Uses config internally

async def handle_add_logic(parts: list, bookmark_storage, alias_pattern: re.Pattern, logger) -> bool:
    """
    Handles the 'zira bookmark add <alias> <path>' command logic.
    """
    if len(parts) < 5:
        await speak("Usage: zira bookmark add <alias> <path>")
        logger.warning("Bookmark add command missing arguments.")
        return True

    raw_alias = parts[3].strip()
    alias = raw_alias.strip("<>").strip()

    # Security: Validate alias syntax
    if not alias:
        await speak("Bookmark alias cannot be empty.")
        return True
    if not alias_pattern.fullmatch(alias):
        await speak("Invalid alias. Use only letters, numbers, hyphens, or underscores.")
        logger.warning("Attempted to add bookmark with invalid alias: '%s'", alias)
        return True

    raw_path = " ".join(parts[4:]).strip()
    path = raw_path.strip("<>").strip()

    if not path:
        await speak("Bookmark path cannot be empty.")
        return True

    # Security: Normalize path to absolute and expand user/environment variables.
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not os.path.isabs(path):
        path = os.path.abspath(path)

    # Informative warning if the path doesn’t exist; saving is still allowed.
    if not os.path.exists(path):
        warning_msg = f"Warning: Path '{path}' does not currently exist."
        print(Fore.YELLOW + warning_msg + Style.RESET_ALL)
        await speak(warning_msg)
        logger.warning("Bookmark added with non-existent path: '%s'", path)

    bookmarks = await bookmark_storage.load_bookmarks()
    
    # Security: Prevent overwriting existing bookmarks without explicit removal
    if alias in bookmarks:
        await speak(
            f"Bookmark '{alias}' already exists. To overwrite, remove it first or choose a new alias."
        )
        logger.info("Attempted to add existing bookmark alias: '%s'", alias)
        return True

    bookmarks[alias] = path
    try:
        await bookmark_storage.save_bookmarks(bookmarks)
    except Exception:
        await speak(
            "Could not save the bookmark due to a file error. Check disk space or permissions."
        )
        return True

    await speak(f"Bookmark '{alias}' added for path: {path}")
    logger.info("Bookmark added: %s -> %s", alias, path)
    return True
