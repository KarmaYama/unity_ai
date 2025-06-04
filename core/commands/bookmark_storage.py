import json
import os
import asyncio
from datetime import datetime
from colorama import Fore, Style
from core.config import Config # For logging and potentially config-driven paths

# Path to the bookmarks JSON file (relative to project root; can make absolute if preferred)
BOOKMARKS_FILE = "bookmarks.json"

def _datetime_now_str() -> str:
    """
    Returns a filesystem-safe timestamp, e.g. "2025-06-03T15-30-00"
    Used when making backups of corrupted JSON.
    """
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


class BookmarkStorage:
    """
    Handles persistent storage for bookmarks, including loading, saving,
    and managing the JSON file.

    Security Considerations:
    - Atomic Writes: Uses temp file + os.replace() to prevent data corruption
      from partial writes if the application crashes during a save.
    - Strict File Permissions: Sets 0o600 (read/write only for owner) on the
      bookmarks file and its backups to restrict unauthorized access.
    - Corruption Handling: Renames corrupted JSON files to timestamped .bak files
      to prevent data loss and allow for manual recovery.
    - Concurrent Access Protection: Uses asyncio.Lock to prevent race conditions
      during file reads/writes, ensuring data integrity.
    - UTF-8 Encoding: Ensures proper handling of various characters without corruption.
    """

    def __init__(self, logger, config: Config):
        self.logger = logger
        self.config = config
        self.bookmarks_path = BOOKMARKS_FILE # Can be made configurable via self.config if preferred

        # Async lock to prevent concurrent reads/writes, crucial for data integrity
        self._file_lock = asyncio.Lock()

    async def load_bookmarks(self) -> dict:
        """
        Loads bookmarks from the JSON file (UTF-8).
        If the file doesn't exist, returns an empty dictionary.
        If decoding fails, renames the corrupted file to a timestamped .bak and starts fresh.
        """
        try:
            async with self._file_lock:
                # Security: Ensure file is opened in read mode ('r')
                with open(self.bookmarks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
        except FileNotFoundError:
            self.logger.info("Bookmarks file not found at %s. Starting with empty bookmarks.", self.bookmarks_path)
            return {}
        except json.JSONDecodeError:
            # Security: Handle corrupted JSON by creating a backup and starting fresh.
            # This prevents infinite loops or crashes due to malformed data.
            bak_name = f"{self.bookmarks_path}.{_datetime_now_str()}.bak"
            self.logger.warning(
                "Could not decode %s. Renaming to %s and starting empty.",
                self.bookmarks_path,
                bak_name
            )
            print(
                Fore.YELLOW
                + f"Warning: Could not decode {self.bookmarks_path}. Renaming to {bak_name} and starting with an empty bookmark list."
                + Style.RESET_ALL
            )
            try:
                os.replace(self.bookmarks_path, bak_name)
                # Security: Set strict permissions on the backup as well
                os.chmod(bak_name, 0o600)
            except Exception as rename_err:
                self.logger.error("Failed to rename corrupted JSON: %s", rename_err, exc_info=True)
            return {}
        except Exception as e:
            self.logger.error("Unexpected error loading bookmarks from %s: %s", self.bookmarks_path, e, exc_info=True)
            print(Fore.RED + f"Error loading bookmarks: {e}" + Style.RESET_ALL)
            return {} # Return empty to allow app to continue
            

    async def save_bookmarks(self, bookmarks: dict):
        """
        Atomically writes bookmarks to the JSON file (UTF-8, ensure_ascii=False).
        Uses a temp file + os.replace to avoid partial writes, then sets file mode to 0o600.
        """
        tmp_path = f"{self.bookmarks_path}.tmp"
        try:
            async with self._file_lock:
                # Security: Write to a temporary file first
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(bookmarks, f, ensure_ascii=False, indent=4)

                # Security: Atomically replace the old file with the new, fully written one
                os.replace(tmp_path, self.bookmarks_path)

                # Security: Restrict permissions on the new bookmarks file to owner read/write
                try:
                    os.chmod(self.bookmarks_path, 0o600)
                except Exception as chmod_err:
                    # Log but do not fail if chmod fails, as the file was still saved.
                    self.logger.warning(
                        "Could not set permissions on %s: %s",
                        self.bookmarks_path,
                        chmod_err
                    )

        except Exception as e:
            self.logger.error("Error saving bookmarks to %s: %s", self.bookmarks_path, e, exc_info=True)
            print(Fore.RED + f"Error saving bookmarks: {e}" + Style.RESET_ALL)
            # Re-raise to ensure the calling command handler knows saving failed
            raise 
        finally:
            # Clean up the temporary file if it somehow wasn't replaced (e.g., if os.replace failed)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as cleanup_err:
                    self.logger.error("Failed to clean up temp bookmark file %s: %s", tmp_path, cleanup_err)

