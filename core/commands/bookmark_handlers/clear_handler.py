#core/commands/bookmark_handers/clear_handler.py

import re
from colorama import Fore, Style
from core.tts import speak # Uses config internally
from core.commands.bookmark_handlers.remove_handler import handle_remove_logic # NEW: Import remove handler

async def handle_clear_logic(parts: list, bookmark_storage, alias_pattern: re.Pattern, logger) -> bool:
    """
    Handles the 'zira bookmark clear' (all) or 'zira bookmark clear <alias>' (specific) command logic.
    """
    logger.debug("handle_clear_logic called with parts: %s", parts)

    # Determine if clearing all or a specific alias
    # If len(parts) <= 3, it means the command was "zira bookmark clear" (no alias provided)
    is_clear_all = len(parts) <= 3 
    alias_to_clear = None

    if not is_clear_all:
        raw_alias = " ".join(parts[3:]).strip()
        alias_to_clear = raw_alias.strip("<>").strip()

        # If an alias was intended but is empty after stripping, treat as clear all
        if not alias_to_clear:
            is_clear_all = True
        elif not alias_pattern.fullmatch(alias_to_clear):
            await speak("Invalid alias format. Please provide a valid bookmark alias to clear.")
            logger.warning("Attempted to clear bookmark with invalid alias format: '%s'", raw_alias)
            return True

    # --- Clear All Logic ---
    if is_clear_all:
        bookmarks = await bookmark_storage.load_bookmarks() # Load only if clearing all
        if not bookmarks:
            print(Fore.CYAN + "No bookmarks to clear." + Style.RESET_ALL)
            await speak("There are no bookmarks to clear.")
            logger.info("Clear all bookmarks requested, but no bookmarks existed.")
            return True

        # Confirmation if many bookmarks
        if len(bookmarks) > 3:
            print(Fore.YELLOW + "You have more than 3 bookmarks. Are you sure you want to clear all? (yes/no)" + Style.RESET_ALL)
            confirm = input("Confirm clear all: ").strip().lower()
            if confirm not in ("yes", "y"):
                await speak("Clear operation cancelled.")
                logger.info("Clear all bookmarks operation cancelled by user.")
                return True

        try:
            await bookmark_storage.save_bookmarks({}) # Save an empty dictionary to clear all
        except Exception:
            await speak(
                "Could not clear bookmarks due to a file error. Check disk space or permissions."
            )
            logger.error("Failed to clear all bookmarks due to file error.", exc_info=True)
            return True

        print(Fore.CYAN + "All bookmarks have been cleared." + Style.RESET_ALL)
        await speak("All bookmarks have been cleared.")
        logger.info("All bookmarks cleared.")
        return True
    # --- Clear Specific Alias Logic (reusing remove_handler) ---
    else:
        # Construct 'parts' suitable for handle_remove_logic.
        # handle_remove_logic expects parts[3] to be the alias.
        # So, we pass a dummy 'parts' list, where the alias is at index 3.
        # Example: ['zira', 'bookmark', 'remove', 'my_alias']
        mock_parts = ["zira", "bookmark", "remove", alias_to_clear]
        
        # Call the existing handle_remove_logic
        return await handle_remove_logic(mock_parts, bookmark_storage, logger)

