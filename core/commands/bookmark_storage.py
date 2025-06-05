#core/commands/bookmark_storage.py

# core/commands/bookmark_storage.py

import json
import os
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style
from core.config import Config
from tools.agent_tools import _ALLOWED_DATA_ROOT, _is_safe_path  # Import path validation helpers

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
    - Atomic Writes: Uses temp file + os.replace() (or pathlib.replace()) to prevent data corruption
      from partial writes if the application crashes during a save.
    - Strict File Permissions: Sets 0o600 (read/write only for owner) on the
      bookmarks file and its backups to restrict unauthorized access.
    - Corruption Handling: Renames corrupted JSON files to timestamped .bak files
      to prevent data loss and allow for manual recovery.
    - Concurrent Access Protection: Uses asyncio.Lock to prevent race conditions
      during file reads/writes, ensuring data integrity.
    - UTF-8 Encoding: Ensures proper handling of various characters without corruption.
    - Path Validation: Ensures the bookmark file path is canonicalized and restricted
      to a safe data directory, preventing path traversal vulnerabilities.
    """

    def __init__(self, logger, config: Config):
        self.logger = logger
        self.config = config

        # Retrieve configured path (expecting a relative path under _ALLOWED_DATA_ROOT)
        configured_path = self.config.BOOKMARKS_FILE_PATH
        if not isinstance(configured_path, str) or not configured_path.strip():
            raise RuntimeError("Config.BOOKMARKS_FILE_PATH must be a non-empty string.")

        # Prevent absolute paths by normalizing
        if os.path.isabs(configured_path):
            raise RuntimeError(
                f"Bookmark file path '{configured_path}' must be relative to the allowed data directory."
            )

        # Construct the full absolute path relative to _ALLOWED_DATA_ROOT
        abs_path = os.path.join(_ALLOWED_DATA_ROOT, configured_path)
        # Canonicalize for consistent comparison and safety
        self.bookmarks_path = os.path.realpath(abs_path)

        # Validate that bookmarks_path resides under the allowed data root
        if not _is_safe_path(_ALLOWED_DATA_ROOT, self.bookmarks_path, self.logger):
            raise RuntimeError(
                f"Bookmark file path '{configured_path}' resolves to an unsafe location: {self.bookmarks_path}. "
                "It must be within the allowed data directory."
            )
        self.logger.info("Bookmark file path set to: %s", self.bookmarks_path)

        # Ensure parent directory exists with restrictive permissions (0o700)
        parent_dir = os.path.dirname(self.bookmarks_path)
        try:
            os.makedirs(parent_dir, mode=0o700, exist_ok=True)
            os.chmod(parent_dir, 0o700)
        except Exception as e:
            self.logger.error("Failed to create or lock down directory '%s': %s", parent_dir, e, exc_info=True)
            raise

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
                # Security: Open in read mode only
                with open(self.bookmarks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
        except FileNotFoundError:
            self.logger.info("Bookmarks file not found at %s. Starting with empty bookmarks.", self.bookmarks_path)
            return {}
        except json.JSONDecodeError:
            # Corrupted JSON: back it up and start fresh
            bak_name = f"{self.bookmarks_path}.{_datetime_now_str()}.bak"
            self.logger.warning(
                "Could not decode %s. Renaming to %s and starting empty.",
                self.bookmarks_path,
                bak_name,
            )
            print(
                Fore.YELLOW
                + f"Warning: Could not decode {self.bookmarks_path}. Renaming to {bak_name} and starting with an empty bookmark list."
                + Style.RESET_ALL
            )
            try:
                # Atomic rename of corrupted file
                os.replace(self.bookmarks_path, bak_name)
                os.chmod(bak_name, 0o600)
            except Exception as rename_err:
                self.logger.error("Failed to rename corrupted JSON '%s' → '%s': %s", self.bookmarks_path, bak_name, rename_err, exc_info=True)
            return {}
        except Exception as e:
            self.logger.error("Unexpected error loading bookmarks from %s: %s", self.bookmarks_path, e, exc_info=True)
            print(Fore.RED + f"Error loading bookmarks: {e}" + Style.RESET_ALL)
            return {}

    async def save_bookmarks(self, bookmarks: dict):
        """
        Atomically writes bookmarks to the JSON file (UTF-8, ensure_ascii=False).
        Uses a temp file + os.replace() to avoid partial writes, then sets file mode to 0o600.
        """
        tmp_path = None
        try:
            async with self._file_lock:
                # Write to a secure temporary file in the same directory
                parent_dir = os.path.dirname(self.bookmarks_path)
                with tempfile.NamedTemporaryFile(
                    mode="w", 
                    encoding="utf-8", 
                    dir=parent_dir, 
                    delete=False,
                    prefix="._bookmarks_tmp_",
                    suffix=".json"
                ) as tmp_file:
                    tmp_path = tmp_file.name
                    # Dump JSON with indent for readability
                    json.dump(bookmarks, tmp_file, ensure_ascii=False, indent=4)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())

                # Atomic replace old file with new one
                os.replace(tmp_path, self.bookmarks_path)

                # Restrict permissions on the new bookmarks file
                try:
                    os.chmod(self.bookmarks_path, 0o600)
                except Exception as chmod_err:
                    self.logger.warning(
                        "Could not set permissions on '%s': %s", self.bookmarks_path, chmod_err
                    )

        except Exception as e:
            self.logger.error("Error saving bookmarks to %s: %s", self.bookmarks_path, e, exc_info=True)
            print(Fore.RED + f"Error saving bookmarks: {e}" + Style.RESET_ALL)
            raise
        finally:
            # Clean up the temporary file if it still exists (e.g., if os.replace failed)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as cleanup_err:
                    self.logger.error("Failed to clean up temp bookmark file '%s': %s", tmp_path, cleanup_err)

