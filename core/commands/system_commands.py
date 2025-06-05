# core/commands/system_commands.py

import re
import asyncio
from colorama import Fore, Style
from core.tts import speak
from core.config import Config 

# Precompiled regex patterns for command parsing
_WEBSITE_REGEX = re.compile(r"^open\s+website\s+(https?://\S+)$", re.IGNORECASE)
_APP_REGEX = re.compile(r"^open\s+(.+)$", re.IGNORECASE)
_CLOSE_REGEX = re.compile(r"^close\s+(.+)$", re.IGNORECASE)
_WEATHER_REGEX = re.compile(r"^(?:weather(?:\s+in)?\s+)(.+)$", re.IGNORECASE)
_SEARCH_REGEX = re.compile(r"^search\s+(.+)$", re.IGNORECASE)
# NEW: Regex for voice mode commands
_ENABLE_VOICE_REGEX = re.compile(r"^(?:enable|activate)\s+voice\s+mode$", re.IGNORECASE)
_DISABLE_VOICE_REGEX = re.compile(r"^(?:disable|deactivate|exit)\s+voice\s+mode$", re.IGNORECASE)


class SystemCommands:
    """
    Handles system-level commands: opening/closing applications, opening websites,
    getting weather, and performing searches. Delegates execution to securely
    implemented tools and sanitizes inputs.
    """

    # UPDATED: Add voice_flag_ref to the constructor
    def __init__(self, logger, config: Config, tools: dict, search_tool, voice_flag_ref: dict):
        """
        Args:
            logger: Preconfigured logger for auditing and error reporting.
            config: Config object containing all application settings.
            tools: Dictionary mapping tool_key → LangChain Tool object.
            search_tool: DuckDuckGo search function (synchronous) or None.
            voice_flag_ref: A dictionary { "enabled": bool } to control voice mode.
        """
        self.logger = logger
        self.config = config
        self.tools = tools
        self.search_tool = search_tool
        self.voice_flag_ref = voice_flag_ref # Store the reference

    async def _safe_speak(self, text: str):
        """Wrapper around TTS that catches exceptions to prevent crashes."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error("TTS Error: %s", e, exc_info=True)

    async def _invoke_tool(self, tool_key: str, arg: str, error_prefix: str) -> bool:
        """
        Invokes a specified tool asynchronously with a single string argument.
        Prioritizes `.arun(...)` for asynchronous tools, falls back to
        `.run(...)` in a background thread for synchronous ones.
        Returns True on success, False otherwise.
        """
        # Validate types
        if not isinstance(tool_key, str) or not isinstance(arg, str):
            self.logger.error(
                "Invalid types for tool invocation: %s, %s",
                type(tool_key),
                type(arg),
            )
            await self._safe_speak("Internal error: invalid input type.")
            print(Fore.RED + f"{self.config.ASSISTANT_NAME}: Internal error." + Style.RESET_ALL)
            return False

        if tool_key not in self.tools:
            self.logger.error("Attempt to invoke unknown tool: %s", tool_key)
            await self._safe_speak("Sorry, I cannot perform that action.")
            print(Fore.RED + f"{self.config.ASSISTANT_NAME}: Unrecognized tool." + Style.RESET_ALL)
            return False

        tool_instance = self.tools[tool_key]
        try:
            # Prioritize asynchronous invocation if the tool has an 'arun' method
            if hasattr(tool_instance, "arun") and callable(tool_instance.arun):
                self.logger.info(f"Invoking tool '{tool_key}.arun' with argument: '{arg}'")
                result = await tool_instance.arun(arg)
            elif hasattr(tool_instance, "run") and callable(tool_instance.run):
                # Fallback to synchronous invocation in a thread pool for blocking ops
                self.logger.info(f"Invoking tool '{tool_key}.run' (sync via thread) with argument: '{arg}'")
                result = await asyncio.to_thread(tool_instance.run, arg)
            else:
                raise AttributeError(f"Tool '{tool_key}' has neither 'arun' nor 'run' method.")

            # Successful invocation; log and speak result
            self.logger.debug("%s('%s') -> %s", tool_key, arg, result)
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {result}" + Style.RESET_ALL)
            await self._safe_speak(result)
            return True

        except Exception as e:
            self.logger.error(
                "Error invoking %s with '%s': %s", tool_key, arg, e, exc_info=True
            )
            message = f"{error_prefix} {arg}."
            await self._safe_speak(message)
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {message}" + Style.RESET_ALL)
            return False

    async def handle_open_website(self, command_text: str) -> bool:
        """
        Handles "open website <url>" commands by delegating to the open_website tool.
        """
        m = _WEBSITE_REGEX.match(command_text.strip())
        if not m:
            return False

        url = m.group(1).strip()
        if len(url) > 2083:  # Standard max URL length
            msg = "That URL is too long to open safely."
            self.logger.warning("URL too long: %s", url)
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

        self.logger.info("Opening website: %s", url)
        return await self._invoke_tool(
            tool_key="open_website",
            arg=url,
            error_prefix="Sorry, I couldn't open the website"
        )

    async def handle_open_application(self, command_text: str) -> bool:
        """
        Handles "open <application>" commands by delegating to the open_application tool.
        """
        m = _APP_REGEX.match(command_text.strip())
        if not m:
            return False

        app_name = m.group(1).strip()

        # If it looks like a URL, skip so website handler can catch it
        if app_name.startswith("http://") or app_name.startswith("https://"):
            return False

        # Disallow shell-sensitive characters for security
        if any(c in app_name for c in [';', '&', '|', '$', '`', '<', '>']):
            msg = "Invalid application name. Please avoid special characters."
            self.logger.warning("Invalid characters in app_name: %s", app_name)
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

        self.logger.info("Opening application: %s", app_name)
        return await self._invoke_tool(
            tool_key="open_application",
            arg=app_name,
            error_prefix="Sorry, I couldn't open the application"
        )

    async def handle_close_application(self, command_text: str) -> bool:
        """
        Handles "close <application>" commands by delegating to the close_application tool.
        """
        m = _CLOSE_REGEX.match(command_text.strip())
        if not m:
            return False

        app_name = m.group(1).strip()

        # Disallow shell-sensitive characters for security
        if any(c in app_name for c in [';', '&', '|', '$', '`', '<', '>']):
            msg = "Invalid application name. Please avoid special characters."
            self.logger.warning("Invalid characters in app_name for close: %s", app_name)
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

        self.logger.info("Closing application: %s", app_name)
        return await self._invoke_tool(
            tool_key="close_application",
            arg=app_name,
            error_prefix="Sorry, I couldn't close the application"
        )

    async def handle_get_weather(self, command_text: str) -> bool:
        """
        Handles "weather <location>" or "weather in <location>" commands by delegating to the get_weather tool.
        """
        m = _WEATHER_REGEX.match(command_text.strip())
        if not m:
            return False

        location = m.group(1).strip()

        # Disallow suspicious characters to prevent injection/abuse
        if any(c in location for c in [';', '&', '|', '$', '`', '<', '>']):
            msg = "Invalid location. Please avoid special characters."
            self.logger.warning("Invalid characters in location: %s", location)
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

        self.logger.info("Getting weather for: %s", location)
        return await self._invoke_tool(
            tool_key="get_weather",
            arg=location,
            error_prefix="Sorry, I couldn't retrieve weather for"
        )

    async def handle_search(self, command_text: str) -> bool:
        """
        Handles "search <query>" commands by invoking the search_tool in a thread.
        """
        m = _SEARCH_REGEX.match(command_text.strip())
        if not m:
            return False

        query = m.group(1).strip()
        if not query:
            msg = "Please provide a search query."
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

        self.logger.info("Performing search for: %s", query)

        if not self.search_tool:
            msg = "Search functionality is not available."
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

        try:
            # If search_tool is a synchronous callable, run it in a thread
            result = await asyncio.to_thread(self.search_tool, query)
            self.logger.debug("Search result for '%s': %s", query, result)
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {result}" + Style.RESET_ALL)
            await self._safe_speak(result)
        except Exception as e:
            self.logger.error("Search error for '%s': %s", query, e, exc_info=True)
            msg = "Sorry, I couldn't perform the search."
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)

        return True

    # NEW: Voice mode toggle commands
    async def handle_enable_voice_mode(self, command_text: str) -> bool:
        """
        Handles "enable voice mode" command.
        """
        if not _ENABLE_VOICE_REGEX.match(command_text.strip()):
            return False

        if self.voice_flag_ref.get("enabled"):
            msg = "Voice mode is already enabled."
            self.logger.info(msg)
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True
        else:
            self.voice_flag_ref["enabled"] = True
            msg = "Voice mode enabled. Press and hold your push-to-talk key to speak."
            self.logger.info(msg)
            print(Fore.GREEN + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

    async def handle_disable_voice_mode(self, command_text: str) -> bool:
        """
        Handles "disable voice mode" command.
        """
        if not _DISABLE_VOICE_REGEX.match(command_text.strip()):
            return False

        if not self.voice_flag_ref.get("enabled"):
            msg = "Voice mode is already disabled."
            self.logger.info(msg)
            print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True
        else:
            self.voice_flag_ref["enabled"] = False
            msg = "Voice mode disabled. Returning to text input."
            self.logger.info(msg)
            print(Fore.GREEN + f"{self.config.ASSISTANT_NAME}: {msg}" + Style.RESET_ALL)
            await self._safe_speak(msg)
            return True

