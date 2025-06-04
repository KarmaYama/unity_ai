import re
from colorama import Fore, Style
from core.tts import speak  # TTS wrapper (uses config internally)
from core.config import Config  # To read any config settings if needed
from core.commands.bookmark_storage import BookmarkStorage # Import the storage class

# Import the individual command handler functions
from core.commands.bookmark_handlers.add_handler import handle_add_logic
from core.commands.bookmark_handlers.list_handler import handle_list_logic
from core.commands.bookmark_handlers.jump_handler import handle_jump_logic
from core.commands.bookmark_handlers.remove_handler import handle_remove_logic
from core.commands.bookmark_handlers.clear_handler import handle_clear_logic


class BookmarkCommands:
    """
    Orchestrates all bookmark-related commands.
    Delegates specific command logic to dedicated handler modules.
    """

    def __init__(self, logger, config: Config):
        self.logger = logger
        self.config = config
        
        # Instantiate the BookmarkStorage class once
        self.bookmark_storage = BookmarkStorage(logger=self.logger, config=self.config)

        # Alias pattern for validation, shared with handlers that need it
        self._alias_pattern = re.compile(r"^[A-Za-z0-9_-]+$")

    # The _safe_speak wrapper remains here as it's a common utility for all handlers
    # that need to speak, and it handles logging errors centrally.
    async def _safe_speak(self, text: str):
        """Wrapper around TTS that never crashes the assistant."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error("TTS Error: %s", e, exc_info=True)

    # --- Command Dispatchers ---

    async def handle_add(self, parts: list) -> bool:
        """Dispatches to the add bookmark logic."""
        return await handle_add_logic(parts, self.bookmark_storage, self._alias_pattern, self.logger)

    async def handle_list(self, parts: list) -> bool:
        """Dispatches to the list bookmarks logic."""
        return await handle_list_logic(self.bookmark_storage, self.logger)

    async def handle_jump(self, parts: list) -> bool:
        """Dispatches to the jump bookmark logic."""
        return await handle_jump_logic(parts, self.bookmark_storage, self.logger)

    async def handle_remove(self, parts: list) -> bool:
        """Dispatches to the remove bookmark logic."""
        return await handle_remove_logic(parts, self.bookmark_storage, self.logger)

    async def handle_clear(self, parts: list) -> bool:
        """Dispatches to the clear bookmarks logic (all or specific)."""
        return await handle_clear_logic(parts, self.bookmark_storage, self._alias_pattern, self.logger)

