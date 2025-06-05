# core/handler_system.py

import re
from difflib import get_close_matches
from colorama import Fore, Style

from langchain.schema import HumanMessage
from core.commands.bookmark_commands import BookmarkCommands
from core.commands.system_commands import SystemCommands 


class SystemHandler:
    """
    Handles all deterministic, “system‐level” commands:
      - Voice mode toggles
      - Help text
      - Bookmarks (zira bookmark …)
      - Open/close application
      - Weather
      - Web search
    """

    def __init__(self, tools: dict, search_tool, logger, voice_flag_ref: dict, config):
        self.tools = tools
        self.search_tool = search_tool
        self.logger = logger
        self.voice_flag_ref = voice_flag_ref
        self.config = config

        self.bookmark_commands = BookmarkCommands(logger=logger, config=config)

        self.system_commands = SystemCommands(
            logger=logger,
            config=config,
            tools=tools,
            search_tool=search_tool,
            voice_flag_ref=voice_flag_ref 
        )

        self._bookmark_registry = {
            "add": self.bookmark_commands.handle_add,
            "list": self.bookmark_commands.handle_list,
            "jump": self.bookmark_commands.handle_jump,
            "remove": self.bookmark_commands.handle_remove,
            "clear": self.bookmark_commands.handle_clear,
        }

    async def try_handle(self, command_text: str) -> bool:
        """
        Attempt to process `command_text` via deterministic rules.
        Returns True if handled; otherwise False.
        """
        sanitized_input = re.sub(r"\s+", " ", command_text).strip()
        lower = sanitized_input.lower()
        parts = sanitized_input.split()

        # ── Voice Mode Toggles ──
        # UPDATED: Delegate to system_commands for voice mode toggles
        if await self.system_commands.handle_enable_voice_mode(sanitized_input):
            self.logger.info("System command: enable voice mode handled.")
            return True

        if await self.system_commands.handle_disable_voice_mode(sanitized_input):
            self.logger.info("System command: disable voice mode handled.")
            return True

        # ── Help Command ──
        if lower in ["zira help", "help zira", "help"]:
            help_text = (
                "You can say:\n"
                "  • zira bookmark add <alias> <path>\n"
                "  • zira bookmark list\n"
                "  • zira bookmark jump <alias>\n"
                "  • zira bookmark remove <alias>\n"
                "  • zira bookmark clear [<alias>]\n"
                "  • zira open <application or website>\n"
                "  • zira close <application>\n"
                "  • zira weather in <city>\n"
                "  • zira search <query>\n"
                "  • enable voice mode / disable voice mode\n"
                "Type any other question and I’ll try to help via LLM."
            )
            print(Fore.CYAN + help_text + Style.RESET_ALL)
            self.logger.info("Help text displayed.")
            return True

       
        if await self.system_commands.handle_open_website(sanitized_input):
            self.logger.info("System command: open_website handled.")
            return True
        if await self.system_commands.handle_open_application(sanitized_input):
            self.logger.info("System command: open_application handled.")
            return True
        if await self.system_commands.handle_close_application(sanitized_input):
            self.logger.info("System command: close_application handled.")
            return True
        if await self.system_commands.handle_get_weather(sanitized_input):
            self.logger.info("System command: get_weather handled.")
            return True
        if await self.system_commands.handle_search(sanitized_input):
            self.logger.info("System command: search handled.")
            return True

        # ── Bookmark Commands ──
        if len(parts) >= 2 and parts[0].lower() == "zira" and parts[1].lower() == "bookmark":
            self.logger.info("Bookmark command detected.")
            if len(parts) < 3:
                usage = (
                    "Usage:\n"
                    "  zira bookmark add <alias> <path>\n"
                    "  zira bookmark list\n"
                    "  zira bookmark jump <alias>\n"
                    "  zira bookmark remove <alias>\n"
                    "  zira bookmark clear [<alias>]"
                )
                print(Fore.YELLOW + usage + Style.RESET_ALL)
                return True

            raw_subcommand = parts[2].lower()
            valid_subcommands = list(self._bookmark_registry.keys())
            matches = get_close_matches(raw_subcommand, valid_subcommands, n=1, cutoff=0.75)
            if matches:
                chosen = matches[0]
                if chosen != raw_subcommand:
                    notice = f"Interpreting '{raw_subcommand}' as '{chosen}'."
                    print(Fore.YELLOW + notice + Style.RESET_ALL)
                handler_fn = self._bookmark_registry[chosen]
                self.logger.info(f"Bookmark subcommand '{chosen}' -> invoking handler.")
                await handler_fn(parts)
                return True

            print(Fore.RED + f"Unknown bookmark command: '{raw_subcommand}'" + Style.RESET_ALL)
            return True

        return False
