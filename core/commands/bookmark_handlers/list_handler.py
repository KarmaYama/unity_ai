#core/commands/bookmark_handers/list_handler.py

from colorama import Fore, Style
from core.tts import speak # Uses config internally

async def handle_list_logic(bookmark_storage, logger) -> bool:
    """
    Handles the 'zira bookmark list' command logic.
    """
    bookmarks = await bookmark_storage.load_bookmarks()
    if not bookmarks:
        await speak("You haven't saved any bookmarks yet.")
        logger.info("Bookmark list requested, but no bookmarks found.")
        return True

    print(Fore.CYAN + "── Saved Bookmarks ──" + Style.RESET_ALL)
    for alias, path in bookmarks.items():
        print(f"{Fore.GREEN}{alias}{Style.RESET_ALL}: {Fore.BLUE}{path}{Style.RESET_ALL}")
    await speak("Here are your saved bookmarks.")
    logger.info("Bookmark list displayed.")
    return True
