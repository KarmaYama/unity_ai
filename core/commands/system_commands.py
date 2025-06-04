import re
from colorama import Fore, Style
from core.tts import speak
from core.config import Config
import os # Added for potential future security checks, though not used in this iteration.

# Precompiled regex patterns for command parsing. These are safe as they only extract text.
_WEBSITE_REGEX = re.compile(r"^open\s+website\s+(https?://\S+)", re.IGNORECASE)
_APP_REGEX     = re.compile(r"^open\s+(.+)$",                         re.IGNORECASE)
_CLOSE_REGEX   = re.compile(r"^close\s+(.+)$",                        re.IGNORECASE)
_WEATHER_REGEX = re.compile(r"^(?:weather(?:\s+in)?\s+)(.+)$",        re.IGNORECASE)
_SEARCH_REGEX  = re.compile(r"^search\s+(.+)$",                       re.IGNORECASE)

class SystemCommands:
    """
    Handles system-level commands like opening websites, applications, getting weather, and search.
    Delegates actual execution to specialized tools.
    """
    def __init__(self, logger, config: Config, tools: dict, search_tool):
        self.logger = logger
        self.config = config
        # Tools are expected to be LangChain Tool objects or similar callables
        # that implement their own secure handling of inputs.
        self.tools = tools
        self.search_tool = search_tool

    async def _safe_speak(self, text: str):
        """Wrapper around TTS that doesn’t throw, ensuring robust audio output."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error("TTS Error: %s", e, exc_info=True)
            # Fail-secure: If TTS fails, the system should still continue operating
            # and inform via print.

    async def _invoke_tool(self, tool_key: str, arg: str, error_prefix: str) -> bool:
        """
        Invokes a specified tool with an argument.
        This method acts as a secure intermediary, logging and handling errors.
        It relies on the individual tools (defined in tools/system_tools.py)
        to perform their own robust input validation and command execution.

        Security Considerations:
        - Agent Tool Scope Restrictions: Assumes `self.tools` contains only narrowly
          scoped tools. Avoid generic "shell" tools here.
        - Least-Privilege Execution: The underlying tools should ideally run
          subprocesses with minimal necessary permissions. (Comment for deployment).
        - Fail-Secure Error Handling: Catches broad exceptions, provides a
          user-friendly message, and logs detailed errors internally without exposing them.
        - Sanitized Logging: Ensures tool invocation details are logged, but
          care should be taken not to log overly sensitive `arg` data if it
          were to contain PII or secrets (e.g., if a tool took a password).
          For current tools (URL, app name), this is generally safe.
        """
        # Input Validation & Sanitization (Pre-invocation):
        # Arguments are strings from regex matches. Further validation/sanitization
        # (e.g., URL scheme validation, app name whitelisting) should ideally occur
        # within the *tool* itself, as it has domain-specific knowledge.
        if not isinstance(tool_key, str) or not isinstance(arg, str):
            self.logger.error(f"Invalid tool_key or arg type: {tool_key=}, {arg=}")
            await self._safe_speak("An internal error occurred due to invalid input type.")
            print(Fore.RED + f"{self.config.ASSISTANT_NAME}: An internal error occurred." + Style.RESET_ALL)
            return False

        try:
            # Ensure the tool exists in the registry to prevent arbitrary calls
            if tool_key not in self.tools:
                self.logger.error(f"Attempted to invoke unknown tool: {tool_key}")
                await self._safe_speak("Sorry, that command uses an unrecognized internal tool.")
                print(Fore.RED + f"{self.config.ASSISTANT_NAME}: Unrecognized internal tool." + Style.RESET_ALL)
                return False

            result = await self.tools[tool_key].ainvoke(arg)
            self.logger.debug(f"{tool_key}('{arg}') -> {result}")
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {result}" + Style.RESET_ALL)
            await self._safe_speak(result) # Added _safe_speak here for success messages
            return True
        except Exception as e:
            # Fail-Secure Error Handling: Catch specific exceptions if possible,
            # otherwise provide generic user feedback. Avoid exposing raw stack traces.
            self.logger.error(f"Error in {tool_key} with argument '{arg}': {e}", exc_info=True)
            message = f"{error_prefix} {arg}." # User-friendly message
            await self._safe_speak(message)
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {message}" + Style.RESET_ALL)
            return False

    async def handle_open_website(self, command_text: str) -> bool:
        """
        Handles commands to open websites.
        Delegates to the 'open_website' tool.
        """
        m = _WEBSITE_REGEX.match(command_text)
        if m:
            url = m.group(1)
            # Input Validation: Basic URL scheme check is done by regex.
            # The 'open_website' tool is responsible for robust URL validation,
            # ensuring it's not a local file path, and handling safe browser invocation.
            self.logger.info(f"Attempting to open website: {url}") # Audit trail
            return await self._invoke_tool("open_website", url, "Sorry, I couldn't open the website")
        return False

    async def handle_open_application(self, command_text: str) -> bool:
        """
        Handles commands to open applications.
        Delegates to the 'open_application' tool.
        """
        m = _APP_REGEX.match(command_text)
        if m:
            app_name = m.group(1).strip()
            # Guard against accidentally catching a website
            if app_name.startswith("http://") or app_name.startswith("https://"):
                return False
            # Command Execution & Whitelisting:
            # CRITICAL: The 'open_application' tool MUST implement a strict whitelist
            # of allowed applications to prevent arbitrary command execution.
            # Do NOT allow direct execution of 'app_name' without validation.
            self.logger.info(f"Attempting to open application: {app_name}") # Audit trail
            return await self._invoke_tool("open_application", app_name, "Sorry, I couldn't open the application")
        return False

    async def handle_close_application(self, command_text: str) -> bool:
        """
        Handles commands to close applications.
        Delegates to the 'close_application' tool.
        """
        m = _CLOSE_REGEX.match(command_text)
        if m:
            app_name = m.group(1).strip()
            # Command Execution & Whitelisting:
            # CRITICAL: Similar to 'open_application', the 'close_application' tool
            # MUST implement a strict whitelist of allowed applications to close.
            # Do NOT allow direct execution of 'app_name' without validation.
            self.logger.info(f"Attempting to close application: {app_name}") # Audit trail
            return await self._invoke_tool("close_application", app_name, "Sorry, I couldn't close the application")
        return False

    async def handle_get_weather(self, command_text: str) -> bool:
        """
        Handles commands to get weather information.
        Delegates to the 'get_weather' tool.
        """
        m = _WEATHER_REGEX.match(command_text)
        if m:
            location = m.group(1).strip()
            # Input Validation: The 'get_weather' tool is responsible for
            # sanitizing the location string before passing it to an external API.
            # Network & API Call Security: The 'get_weather' tool should also
            # handle HTTPS enforcement, API response validation, and throttling.
            self.logger.info(f"Attempting to get weather for: {location}") # Audit trail
            return await self._invoke_tool("get_weather", location, "Sorry, I couldn't retrieve weather for")
        return False

    async def handle_search(self, command_text: str) -> bool:
        """
        Handles commands to perform a web search.
        Uses the DuckDuckGo search tool if available.
        """
        m = _SEARCH_REGEX.match(command_text)
        if m:
            query = m.group(1).strip()
            # Input Validation: The search tool is responsible for sanitizing the
            # query string before passing it to the search engine.
            # Network & API Call Security: The search tool should handle HTTPS
            # enforcement, API response validation, and throttling.
            if self.search_tool:
                self.logger.info(f"Performing search for: '{query}'") # Audit trail
                try:
                    result = await self.search_tool(query)
                    print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {result}" + Style.RESET_ALL)
                    await self._safe_speak(result)
                except Exception as e:
                    # Fail-Secure Error Handling: Provide generic user feedback.
                    self.logger.error(f"Search error for query '{query}': {e}", exc_info=True)
                    resp = "Sorry, I couldn't perform the search."
                    await self._safe_speak(resp)
                    print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
                return True
            else:
                message = "The search tool is not available."
                await self._safe_speak(message)
                print(Fore.YELLOW + f"{self.config.ASSISTANT_NAME}: {message}" + Style.RESET_ALL)
                return True
        return False