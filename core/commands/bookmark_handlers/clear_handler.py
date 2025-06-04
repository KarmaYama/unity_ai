import re
from colorama import Fore, Style
from core.tts import speak # Uses config internally

async def handle_clear_logic(parts: list, bookmark_storage, alias_pattern: re.Pattern, logger) -> bool:
    """
    Handles the 'zira bookmark clear' (all) or 'zira bookmark clear <alias>' (specific) command logic.
    """
    logger.debug("handle_clear_logic called with parts: %s", parts)

    bookmarks = await bookmark_storage.load_bookmarks()

    # Determine if clearing all or a specific alias
    # If len(parts) <= 3, it means the command was "zira bookmark clear" (no alias provided)
    is_clear_all = len(parts) <= 3 
    alias_to_clear = None

    if not is_clear_all:
        raw_alias = " ".join(parts[3:]).strip()
        alias_to_clear = raw_alias.strip("<>").strip()

        # Validate alias syntax if provided
        if not alias_to_clear: # This means "zira bookmark clear <>" or "zira bookmark clear "
            is_clear_all = True # Treat as clear all if alias is empty after stripping
        elif not alias_pattern.fullmatch(alias_to_clear):
            await speak("Invalid alias. Please provide a valid bookmark alias to clear.")
            logger.warning("Attempted to clear bookmark with invalid alias: '%s'", alias_to_clear)
            return True

    if is_clear_all:
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
            return True

        print(Fore.CYAN + "All bookmarks have been cleared." + Style.RESET_ALL)
        await speak("All bookmarks have been cleared.")
        logger.info("All bookmarks cleared.")
        return True
    else: # Clear a specific alias
        if alias_to_clear not in bookmarks:
            print(Fore.RED + f"Bookmark '{alias_to_clear}' not found. Nothing to clear." + Style.RESET_ALL)
            await speak(f"Bookmark '{alias_to_clear}' not found. Nothing to clear.")
            logger.warning("Attempted to clear non-existent bookmark: '%s'", alias_to_clear)
            return True

        removed_path = bookmarks.pop(alias_to_clear)
        try:
            await bookmark_storage.save_bookmarks(bookmarks)
        except Exception:
            await speak(
                "Could not update bookmarks due to a file error. Check disk space or permissions."
            )
            return True

        print(Fore.CYAN + f"Bookmark '{alias_to_clear}' for path '{removed_path}' has been cleared." + Style.RESET_ALL)
        await speak(f"Bookmark '{alias_to_clear}' for path '{removed_path}' has been cleared.")
        logger.info("Bookmark '%s' cleared.", alias_to_clear)
        return True
