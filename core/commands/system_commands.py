import re
import os
import subprocess
import webbrowser
from colorama import Fore, Style
from core.tts import speak # Assuming speak is accessible or passed in
from core.config import Config # Import Config

# Precompile regexes once:
_WEBSITE_REGEX = re.compile(r"^open\s+website\s+(https?://\S+)", re.IGNORECASE)
_APP_REGEX     = re.compile(r"^open\s+(.+)$",           re.IGNORECASE)
_CLOSE_REGEX   = re.compile(r"^close\s+(.+)$",          re.IGNORECASE)
_WEATHER_REGEX = re.compile(r"^(?:weather(?:\s+in)?\s+)(.+)$", re.IGNORECASE)
_SEARCH_REGEX  = re.compile(r"^search\s+(.+)$",           re.IGNORECASE)

class SystemCommands:
    """
    Handles system-level commands like opening/closing applications/websites,
    getting weather, and performing searches.
    """
    def __init__(self, logger, config, tools, search_tool):
        self.logger = logger
        self.config = config
        self.tools = tools # System tools like open_application, open_website
        self.search_tool = search_tool # DuckDuckGo search tool

    async def _safe_speak(self, text: str):
        """Wrapper around TTS that doesn’t throw."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error(f"TTS Error: {e}", exc_info=True)

    async def handle_open_website(self, command_text: str):
        """Handles the 'open website <url>' command."""
        m = _WEBSITE_REGEX.match(command_text)
        if m:
            url = m.group(1)
            self.logger.debug(f"Direct invocation: open_website('{url}')")
            try:
                resp = await self.tools["open_website"].ainvoke(url)
                self.logger.debug(f"open_website response: {resp}")
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in open_website: {e}", exc_info=True)
                resp = f"Sorry, I couldn't open the website {url}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            return True
        return False

    async def handle_open_application(self, command_text: str):
        """Handles the 'open <app_name>' command."""
        m = _APP_REGEX.match(command_text)
        if m:
            app_name = m.group(1).strip()
            self.logger.debug(f"Direct invocation: open_application('{app_name}')")
            try:
                resp = await self.tools["open_application"].ainvoke(app_name)
                self.logger.debug(f"open_application response: {resp}")
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in open_application: {e}", exc_info=True)
                resp = f"Sorry, I couldn't open the application {app_name}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            return True
        return False

    async def handle_close_application(self, command_text: str):
        """Handles the 'close <app_name>' command."""
        m = _CLOSE_REGEX.match(command_text)
        if m:
            app_to_close = m.group(1).strip()
            self.logger.debug(f"Direct invocation: close_application('{app_to_close}')")
            try:
                resp = await self.tools["close_application"].ainvoke(app_to_close)
                self.logger.debug(f"close_application response: {resp}")
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in close_application: {e}", exc_info=True)
                resp = f"Sorry, I couldn't close the application {app_to_close}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            return True
        return False

    async def handle_get_weather(self, command_text: str):
        """Handles the 'weather <location>' command."""
        m = _WEATHER_REGEX.match(command_text)
        if m:
            location = m.group(1).strip()
            self.logger.debug(f"Direct invocation: get_weather('{location}')")
            try:
                resp = await self.tools["get_weather"].ainvoke(location)
                self.logger.debug(f"get_weather response: {resp}")
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in get_weather: {e}", exc_info=True)
                resp = f"Sorry, I couldn't retrieve weather for {location}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            return True
        return False

    async def handle_search(self, command_text: str):
        """Handles the 'search <query>' command."""
        m = _SEARCH_REGEX.match(command_text)
        if m:
            query = m.group(1).strip()
            if self.search_tool:
                self.logger.debug(f"Direct invocation: DuckDuckGo Search('{query}')")
                try:
                    results = await self.search_tool(query)
                    self.logger.debug(f"DuckDuckGo Search response: {results}")
                    print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {results}" + Style.RESET_ALL)
                    await self._safe_speak(results)
                except Exception as e:
                    self.logger.error(f"Error in DuckDuckGo Search: {e}", exc_info=True)
                    resp = "Sorry, I couldn't perform the search."
                    await self._safe_speak(resp)
                    print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            else:
                resp = "The search tool is not available."
                await self._safe_speak(resp)
                print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            return True
        return False
