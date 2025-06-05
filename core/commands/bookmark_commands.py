# core/commands/bookmark_commands.py

import re
import os
from colorama import Fore, Style
from core.tts import speak  # TTS wrapper (uses config internally)
from core.config import Config  # To read any config settings if needed
from core.commands.bookmark_storage import BookmarkStorage  # Import the storage class

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

        # Instantiate the BookmarkStorage with path validation
        try:
            self.bookmark_storage = BookmarkStorage(logger=self.logger, config=self.config)
        except Exception as e:
            self.logger.error("Failed to initialize BookmarkStorage: %s", e, exc_info=True)
            raise

        # Alias pattern for validation: only letters, digits, underscore, hyphen
        self._alias_pattern = re.compile(r"^[A-Za-z0-9_-]+$")

    async def _safe_speak(self, text: str):
        """Wrapper around TTS that never crashes the assistant."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error("TTS Error: %s", e, exc_info=True)

    # --- Command Dispatchers ---

    async def handle_add(self, parts: list) -> bool:
        """
        Dispatches to the add bookmark logic.
        Expects parts[0] == 'zira', parts[1] == 'bookmark', parts[2] == 'add',
        parts[3] == alias, parts[4]... the path.
        """
        try:
            # Basic sanity check: must have at least 4 elements: ['zira','bookmark','add','alias',...]
            if not isinstance(parts, list) or len(parts) < 4:
                msg = "Usage: zira bookmark add <alias> <path>"
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            alias = parts[3].strip()
            # Validate alias matches allowed pattern
            if not self._alias_pattern.match(alias):
                msg = "Alias must be alphanumeric (letters, digits, underscore, or hyphen)."
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            # Reconstruct path from remaining parts
            path = " ".join(parts[4:]).strip()
            if not path:
                msg = "Please provide a valid path to bookmark."
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            # Delegate to handler logic
            return await handle_add_logic(parts, self.bookmark_storage, self._alias_pattern, self.logger)

        except Exception as e:
            self.logger.error("Error in handle_add: %s", e, exc_info=True)
            msg = "An error occurred while adding the bookmark."
            print(Fore.RED + msg + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

    async def handle_list(self, parts: list) -> bool:
        """
        Dispatches to the list bookmarks logic.
        Lists all saved bookmarks.
        """
        try:
            # parts are not strictly used for listing, but ensure it's a list
            if not isinstance(parts, list):
                msg = "Internal error listing bookmarks."
                self.logger.error("handle_list called with invalid parts: %s", parts)
                print(Fore.RED + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            return await handle_list_logic(self.bookmark_storage, self.logger)

        except Exception as e:
            self.logger.error("Error in handle_list: %s", e, exc_info=True)
            msg = "An error occurred while listing bookmarks."
            print(Fore.RED + msg + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

    async def handle_jump(self, parts: list) -> bool:
        """
        Dispatches to the jump bookmark logic.
        Expects parts[3] == alias to jump to.
        """
        try:
            if not isinstance(parts, list) or len(parts) < 4:
                msg = "Usage: zira bookmark jump <alias>"
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            alias = parts[3].strip()
            if not self._alias_pattern.match(alias):
                msg = "Alias must be alphanumeric (letters, digits, underscore, or hyphen)."
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            return await handle_jump_logic(parts, self.bookmark_storage, self.logger)

        except Exception as e:
            self.logger.error("Error in handle_jump: %s", e, exc_info=True)
            msg = "An error occurred while jumping to the bookmark."
            print(Fore.RED + msg + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

    async def handle_remove(self, parts: list) -> bool:
        """
        Dispatches to the remove bookmark logic.
        Expects parts[3] == alias to remove.
        """
        try:
            if not isinstance(parts, list) or len(parts) < 4:
                msg = "Usage: zira bookmark remove <alias>"
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            alias = parts[3].strip()
            if not self._alias_pattern.match(alias):
                msg = "Alias must be alphanumeric (letters, digits, underscore, or hyphen)."
                print(Fore.YELLOW + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            return await handle_remove_logic(parts, self.bookmark_storage, self.logger)

        except Exception as e:
            self.logger.error("Error in handle_remove: %s", e, exc_info=True)
            msg = "An error occurred while removing the bookmark."
            print(Fore.RED + msg + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

    async def handle_clear(self, parts: list) -> bool:
        """
        Dispatches to the clear bookmarks logic (clear all or specific).
        Usage: zira bookmark clear [<alias>]
        """
        try:
            if not isinstance(parts, list):
                msg = "Internal error clearing bookmarks."
                self.logger.error("handle_clear called with invalid parts: %s", parts)
                print(Fore.RED + msg + Style.RESET_ALL)
                await self._safe_speak(msg)
                return True

            # If a specific alias is provided, validate it
            if len(parts) >= 4:
                alias = parts[3].strip()
                if not self._alias_pattern.match(alias):
                    msg = "Alias must be alphanumeric (letters, digits, underscore, or hyphen)."
                    print(Fore.YELLOW + msg + Style.RESET_ALL)
                    await self._safe_speak(msg)
                    return True

            return await handle_clear_logic(parts, self.bookmark_storage, self._alias_pattern, self.logger)

        except Exception as e:
            self.logger.error("Error in handle_clear: %s", e, exc_info=True)
            msg = "An error occurred while clearing bookmarks."
            print(Fore.RED + msg + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True
