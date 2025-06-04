from colorama import Fore, Style
from core.tts import speak # Uses config internally

async def handle_remove_logic(parts: list, bookmark_storage, logger) -> bool:
    """
    Handles the 'zira bookmark remove <alias>' command logic.
    """
    if len(parts) < 4:
        await speak("Usage: zira bookmark remove <alias>")
        logger.warning("Bookmark remove command missing alias.")
        return True

    raw_alias = parts[3].strip()
    alias = raw_alias.strip("<>").strip()

    if not alias:
        await speak("Please provide a valid bookmark alias to remove.")
        return True

    bookmarks = await bookmark_storage.load_bookmarks()
    
    if alias not in bookmarks:
        await speak(f"Bookmark '{alias}' not found. Nothing to remove.")
        logger.info("Attempted to remove non-existent bookmark: '%s'", alias)
        return True

    removed_path = bookmarks.pop(alias)
    try:
        await bookmark_storage.save_bookmarks(bookmarks)
    except Exception:
        await speak(
            "Could not update bookmarks due to a file error. Check disk space or permissions."
        )
        return True

    await speak(f"Bookmark '{alias}' for path '{removed_path}' has been removed.")
    logger.info("Bookmark removed: %s -> %s", alias, removed_path)
    return True
