import json
import os
import subprocess
import platform
from colorama import Fore, Style
from core.tts import speak  # Assuming speak is accessible
from core.config import Config  # Import Config if you need config-based paths

# Path to the bookmarks JSON file. You can change to an absolute path if desired.
BOOKMARKS_FILE = "bookmarks.json"


class BookmarkCommands:
    """
    Handles all bookmark-related commands:
      - add    : zira bookmark add <alias> <path>
      - list   : zira bookmark list
      - jump   : zira bookmark jump <alias>
      - remove : zira bookmark remove <alias>
      - clear  : zira bookmark clear [<alias>]   # without alias clears all
    """

    def __init__(self, logger, config: Config):
        self.logger = logger
        self.config = config

        # If you prefer a config-based location, uncomment:
        # base = getattr(self.config, "base_dir", os.getcwd())
        # self.bookmarks_path = os.path.join(base, "bookmarks.json")
        # For now, just use the relative constant:
        self.bookmarks_path = BOOKMARKS_FILE

    async def _safe_speak(self, text: str):
        """Wrapper around TTS that doesn’t throw exceptions."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error(f"TTS Error: {e}", exc_info=True)

    def _load_bookmarks(self) -> dict:
        """
        Loads bookmarks from the JSON file, or returns {} if none exist or file is corrupt.
        If JSON is invalid, renames it to .bak and starts fresh.
        """
        try:
            with open(self.bookmarks_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            self.logger.warning(f"Could not decode {self.bookmarks_path}. Renaming to .bak and starting empty.")
            print(
                Fore.YELLOW
                + f"Warning: Could not decode {self.bookmarks_path}. Renaming to {self.bookmarks_path}.bak and starting with an empty bookmark list."
                + Style.RESET_ALL
            )
            try:
                os.rename(self.bookmarks_path, f"{self.bookmarks_path}.bak")
            except Exception:
                pass
            return {}

    def _save_bookmarks(self, bookmarks: dict):
        """Saves the bookmarks dict to the JSON file."""
        try:
            with open(self.bookmarks_path, "w") as f:
                json.dump(bookmarks, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving bookmarks to {self.bookmarks_path}: {e}", exc_info=True)
            print(Fore.RED + f"Error saving bookmarks: {e}" + Style.RESET_ALL)

    async def handle_add(self, parts: list) -> bool:
        """
        Handles: zira bookmark add <alias> <path>
        - parts[3] => alias (possibly wrapped in < >)
        - parts[4:] => path tokens (possibly wrapped in < >)
        """
        if len(parts) < 5:
            await self._safe_speak("Usage: zira bookmark add <alias> <path>")
            return True

        raw_alias = parts[3].strip()
        alias = raw_alias.strip("<>").strip()

        raw_path = " ".join(parts[4:]).strip()
        path = raw_path.strip("<>").strip()

        if not alias:
            await self._safe_speak("Bookmark alias cannot be empty.")
            return True
        if " " in alias:
            await self._safe_speak("Invalid alias: alias cannot contain spaces.")
            return True
        if not path:
            await self._safe_speak("Bookmark path cannot be empty.")
            return True

        # Expand user home and environment variables
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)

        bookmarks = self._load_bookmarks()
        if alias in bookmarks:
            await self._safe_speak(f"Bookmark '{alias}' already exists. To overwrite, remove it first or choose a new alias.")
            return True

        bookmarks[alias] = path
        self._save_bookmarks(bookmarks)

        await self._safe_speak(f"Bookmark '{alias}' added for path: {path}")
        self.logger.info(f"Bookmark added: {alias} -> {path}")
        return True

    async def handle_list(self, parts: list) -> bool:
        """
        Handles: zira bookmark list
        """
        bookmarks = self._load_bookmarks()
        if not bookmarks:
            await self._safe_speak("You haven't saved any bookmarks yet.")
            return True

        print(Fore.CYAN + "── Saved Bookmarks ──" + Style.RESET_ALL)
        for alias, path in bookmarks.items():
            print(f"{Fore.GREEN}{alias}{Style.RESET_ALL}: {Fore.BLUE}{path}{Style.RESET_ALL}")
        await self._safe_speak("Here are your saved bookmarks.")
        return True

    async def handle_jump(self, parts: list) -> bool:
        """
        Handles: zira bookmark jump <alias>
        - parts[3] => alias (possibly wrapped in < >)
        """
        if len(parts) < 4:
            await self._safe_speak("Usage: zira bookmark jump <alias>")
            return True

        raw_alias = parts[3].strip()
        alias = raw_alias.strip("<>").strip()
        if not alias:
            await self._safe_speak("Please provide a valid bookmark alias.")
            return True

        bookmarks = self._load_bookmarks()
        if alias not in bookmarks:
            await self._safe_speak(f"Bookmark '{alias}' not found.")
            return True

        path = bookmarks[alias]
        await self._safe_speak(f"Opening bookmark '{alias}'.")
        self.logger.info(f"Attempting to open path for alias '{alias}': {path}")
        print(Fore.MAGENTA + f"Attempting to open: {path}" + Style.RESET_ALL)

        # Expand home and env vars again
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)

        if not os.path.exists(path):
            await self._safe_speak(f"Error: Path '{path}' does not exist.")
            self.logger.error(f"Bookmark jump failed: Path '{path}' does not exist.")
            return True

        try:
            system = platform.system()
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
                await self._safe_speak(f"Error: Path '{path}' is not a file or directory.")
                self.logger.error(f"Bookmark jump failed: Path '{path}' is not a valid file/directory.")
        except FileNotFoundError:
            await self._safe_speak("Error: Cannot open the file or folder on your system (no handler found).")
            self.logger.error(f"Bookmark jump failed: No OS handler for '{path}'.")
        except Exception as e:
            await self._safe_speak(f"Could not open path: {e}")
            self.logger.error(f"Error opening path '{path}': {e}", exc_info=True)

        return True

    async def handle_remove(self, parts: list) -> bool:
        """
        Handles: zira bookmark remove <alias>
        - parts[3] => alias (possibly wrapped in < >)
        """
        if len(parts) < 4:
            await self._safe_speak("Usage: zira bookmark remove <alias>")
            return True

        raw_alias = parts[3].strip()
        alias = raw_alias.strip("<>").strip()
        if not alias:
            await self._safe_speak("Please provide a valid bookmark alias to remove.")
            return True

        bookmarks = self._load_bookmarks()
        if alias not in bookmarks:
            await self._safe_speak(f"Bookmark '{alias}' not found. Nothing to remove.")
            return True

        removed_path = bookmarks.pop(alias)
        self._save_bookmarks(bookmarks)

        await self._safe_speak(f"Bookmark '{alias}' for path '{removed_path}' has been removed.")
        self.logger.info(f"Bookmark removed: {alias} -> {removed_path}")
        return True

    async def handle_clear(self, parts: list) -> bool:
        """
        Handles:
          - zira bookmark clear           # clears all bookmarks
          - zira bookmark clear <alias>   # clears only that alias
        """
        # DEBUG: Show that handle_clear is invoked and what parts looks like
        print(Fore.YELLOW + f"[DEBUG] handle_clear invoked with parts: {parts}" + Style.RESET_ALL)

        # Everything after "clear" is treated as 'alias' (joined). If empty, clear all.
        if len(parts) <= 3:
            # No alias provided → clear all
            bookmarks = self._load_bookmarks()
            if not bookmarks:
                print(Fore.CYAN + "No bookmarks to clear." + Style.RESET_ALL)
                await self._safe_speak("There are no bookmarks to clear.")
                return True

            self._save_bookmarks({})
            print(Fore.CYAN + "All bookmarks have been cleared." + Style.RESET_ALL)
            await self._safe_speak("All bookmarks have been cleared.")
            self.logger.info("All bookmarks cleared.")
            return True

        # Join up anything after index 2 ("clear") as the alias string
        raw_alias = " ".join(parts[3:]).strip()
        alias = raw_alias.strip("<>").strip()

        if not alias:
            # User typed something like "zira bookmark clear   " (spaces only)
            # Treat that as "clear all"
            bookmarks = self._load_bookmarks()
            if not bookmarks:
                print(Fore.CYAN + "No bookmarks to clear." + Style.RESET_ALL)
                await self._safe_speak("There are no bookmarks to clear.")
                return True

            self._save_bookmarks({})
            print(Fore.CYAN + "All bookmarks have been cleared." + Style.RESET_ALL)
            await self._safe_speak("All bookmarks have been cleared.")
            self.logger.info("All bookmarks cleared.")
            return True

        # Now clear that specific alias
        bookmarks = self._load_bookmarks()
        if alias not in bookmarks:
            print(Fore.RED + f"Bookmark '{alias}' not found. Nothing to clear." + Style.RESET_ALL)
            await self._safe_speak(f"Bookmark '{alias}' not found. Nothing to clear.")
            return True

        removed_path = bookmarks.pop(alias)
        self._save_bookmarks(bookmarks)

        print(Fore.CYAN + f"Bookmark '{alias}' for path '{removed_path}' has been cleared." + Style.RESET_ALL)
        await self._safe_speak(f"Bookmark '{alias}' for path '{removed_path}' has been cleared.")
        self.logger.info(f"Bookmark '{alias}' cleared.")
        return True
