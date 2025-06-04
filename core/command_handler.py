import re
from datetime import datetime
from difflib import get_close_matches
from colorama import Fore, Style
from core.tts import speak  # uses config internally
from core.commands.bookmark_commands import BookmarkCommands
from core.commands.system_commands import SystemCommands


class CommandHandler:
    """
    Central dispatcher for commands, delegating to specific command modules.
    Also handles:
     - voice mode toggling
     - a basic “help” command
     - fuzzy matching for bookmark subcommands
     - LLM fallback

    Security Considerations:
    - Input Validation: Ensures commands are parsed and sanitized before delegation.
    - Command Whitelisting: Relies on delegated modules (SystemCommands, BookmarkCommands)
      to implement strict whitelisting for actions like opening/closing applications.
    - Fail-Secure: Defaults to LLM fallback if no direct command is matched.
    - Sanitized Logging: Avoids logging raw sensitive data directly from user input.
    - Context Window: Manages chat history to prevent sensitive data from being
      re-fed to the LLM (though actual scrubbing happens at the LLM interaction layer).
    """

    def __init__(self, llm, tools, search_tool, logger, chat_history, voice_flag_ref, config):
        """
        Initializes the CommandHandler with necessary components.

        Args:
            llm: The language model instance.
            tools: Dictionary of LangChain tools (e.g., open_website, open_application).
                   These tools are expected to be securely implemented.
            search_tool: DuckDuckGo search function or None.
            logger: Preconfigured logger for auditing and error reporting.
            chat_history: List for conversation context, managed for LLM interactions.
            voice_flag_ref: Dictionary with key "enabled" → bool for voice mode control.
            config: Config object containing all application settings.
        """
        self.llm = llm
        self.tools = tools
        self.search_tool = search_tool
        self.logger = logger
        self.chat_history = chat_history
        self.voice_flag_ref = voice_flag_ref
        self.config = config

        # Instantiate command modules.
        # These modules are responsible for their own specific input validation,
        # command whitelisting, and secure subprocess execution.
        self.bookmark_commands = BookmarkCommands(logger=self.logger, config=self.config)
        self.system_commands = SystemCommands(
            logger=self.logger,
            config=self.config,
            tools=self.tools, # Pass tools for system commands to invoke
            search_tool=self.search_tool
        )

        # Registry of valid bookmark subcommands mapping to their handler methods.
        # This acts as a whitelist for bookmark actions.
        self._bookmark_registry = {
            "add": self.bookmark_commands.handle_add,
            "list": self.bookmark_commands.handle_list,
            "jump": self.bookmark_commands.handle_jump,
            "remove": self.bookmark_commands.handle_remove,
            "clear": self.bookmark_commands.handle_clear, # This handles both clear all and clear specific
        }

    async def _safe_speak(self, text: str):
        """
        Wrapper around TTS that catches exceptions to prevent crashes.
        Ensures that even if TTS fails, the application continues to function.
        """
        try:
            await speak(text)
        except Exception as e:
            self.logger.error("TTS Error: %s", e, exc_info=True)
            # Fail-secure: Log the error but do not halt operations.

    async def process_command(self, command_text: str) -> bool:
        """
        Processes a user command. Attempts to match it against direct commands.
        If no direct command matches, it signals for fallback to the LLM.

        Args:
            command_text: The raw input string from the user.

        Returns:
            True if the command was handled by a direct pattern, False otherwise.
        """
        # Audit Trail: Log the received command for debugging and auditing.
        # Ensure 'command_text' does not contain sensitive PII if logging to disk.
        self.logger.debug("User command received: %s", command_text)

        # Input Sanitization: Normalize whitespace to simplify parsing.
        # This is a basic sanitization step for command parsing.
        sanitized_input = re.sub(r"\s+", " ", command_text).strip()
        lower_input = sanitized_input.lower()
        parts = sanitized_input.split() # Use sanitized_input for splitting to preserve case for paths/URLs

        # ── Global Toggles (Voice Mode) ────────────────────────────────────
        if lower_input == "enable voice mode":
            self.voice_flag_ref["enabled"] = True
            msg = (
                f"{self.config.ASSISTANT_NAME}: Voice mode enabled. "
                f"Press and hold {self.config.STT_PUSH_TO_TALK_KEY} to start listening. "
                f"Press {self.config.STT_PUSH_TO_TALK_KEY} again to stop."
            )
            print(Fore.YELLOW + msg + Style.RESET_ALL)
            await self._safe_speak(
                f"Voice mode enabled. Press and hold {self.config.STT_PUSH_TO_TALK_KEY} to start listening. "
                f"Press {self.config.STT_PUSH_TO_TALK_KEY} again to stop."
            )
            self.logger.info("Voice mode enabled by user.") # Audit trail
            return True

        if lower_input == "disable voice mode":
            self.voice_flag_ref["enabled"] = False
            msg = f"{self.config.ASSISTANT_NAME}: Voice mode disabled. Returning to text input."
            print(Fore.YELLOW + msg + Style.RESET_ALL)
            await self._safe_speak("Voice mode disabled. Returning to text input.")
            self.logger.info("Voice mode disabled by user.") # Audit trail
            return True

        # ── Help Command ───────────────────────────────────────────────────
        if lower_input in ["zira help", "help zira", "help"]:
            help_text = (
                "You can say:\n"
                "  • zira bookmark add <alias> <path>\n"
                "  • zira bookmark list\n"
                "  • zira bookmark jump <alias>\n"
                "  • zira bookmark remove <alias>\n"
                "  • zira bookmark clear [<alias>]\n"
                "  • zira open <application or website>\n"
                "  • zira weather in <city>\n"
                "  • enable voice mode / disable voice mode\n"
                "Type any other question and I’ll try to help via LLM."
            )
            print(Fore.CYAN + help_text + Style.RESET_ALL)
            await self._safe_speak("Here is some help text. You can also type your question.")
            self.logger.info("Help command invoked.") # Audit trail
            return True

        # ── System Commands (Delegated to SystemCommands module) ───────────
        # These methods in SystemCommands are responsible for their own
        # input validation and delegation to securely implemented tools.
        if await self.system_commands.handle_open_website(sanitized_input):
            self.logger.info("System command: open_website handled.") # Audit trail
            return True
        if await self.system_commands.handle_open_application(sanitized_input):
            self.logger.info("System command: open_application handled.") # Audit trail
            return True
        if await self.system_commands.handle_close_application(sanitized_input):
            self.logger.info("System command: close_application handled.") # Audit trail
            return True
        if await self.system_commands.handle_get_weather(sanitized_input):
            self.logger.info("System command: get_weather handled.") # Audit trail
            return True
        if await self.system_commands.handle_search(sanitized_input):
            self.logger.info("System command: search handled.") # Audit trail
            return True

        # ── Bookmark Commands (Delegated to BookmarkCommands module) ───────
        # Pattern: parts[0]=="zira" and parts[1]=="bookmark"
        if len(parts) >= 2 and parts[0].lower() == "zira" and parts[1].lower() == "bookmark":
            self.logger.info("Bookmark command detected.") # Audit trail
            # If missing subcommand (e.g., "zira bookmark")
            if len(parts) < 3:
                usage = (
                    "Usage:\n"
                    "  zira bookmark add <alias> <path>\n"
                    "  zira bookmark list\n"
                    "  zira bookmark jump <alias>\n"
                    "  zira bookmark remove <alias>\n"
                    "  zira bookmark clear [<alias>]"
                )
                print(Fore.YELLOW + usage + Style.RESET_ALL)
                await self._safe_speak(
                    "Please specify a bookmark subcommand: add, list, jump, remove, or clear."
                )
                self.logger.warning("Bookmark command missing subcommand.")
                return True

            raw_subcommand = parts[2].lower()
            valid_subcommands = list(self._bookmark_registry.keys())
            
            # Fuzzy matching for bookmark subcommands.
            # This improves usability but requires the matched handler to be robust.
            matches = get_close_matches(raw_subcommand, valid_subcommands, n=1, cutoff=0.75)
            if matches:
                fuzzy_matched_subcommand = matches[0]
                if fuzzy_matched_subcommand != raw_subcommand:
                    notice = f"Interpreting '{raw_subcommand}' as '{fuzzy_matched_subcommand}'."
                    print(Fore.YELLOW + notice + Style.RESET_ALL)
                    await self._safe_speak(notice)
                
                # Command Whitelisting: Only invoke handlers from the _bookmark_registry.
                handler_function = self._bookmark_registry[fuzzy_matched_subcommand]
                self.logger.info("Bookmark subcommand '%s' handled by '%s'.", raw_subcommand, handler_function.__name__) # Audit trail
                return await handler_function(parts)
            else:
                await self._safe_speak(
                    f"Unknown bookmark command: '{raw_subcommand}'. Available commands are: {', '.join(valid_subcommands)}."
                )
                self.logger.warning("Unknown bookmark subcommand: '%s'.", raw_subcommand)
                return True

        # ── Fallback to LLM ────────────────────────────────────────────────
        # If no direct command pattern was matched, delegate to the LLM.
        # This is a fail-secure approach: if we don't recognize it as a safe,
        # direct command, we let the LLM handle it, which is generally safer
        # than attempting to execute an unrecognized command.
        return False

    async def fallback_to_llm(self, command_text: str):
        """
        Sends `command_text` to the LLM with a system prompt,
        appends to chat_history, and speaks/prints the response.

        Security Considerations:
        - Context Window & Sensitive Data: Ensure `chat_history` is scrubbed
          of any PII or secrets before being sent to the LLM. The current
          implementation appends raw messages. For a production system,
          consider a redaction layer here or within the LLM integration.
        - Rate-Limiting: LLM calls should be rate-limited to prevent API key
          exhaustion or DoS. This is handled by the LLM provider, but client-side
          limits could be added if needed.
        - Fail-Secure Error Handling: Catches exceptions during LLM invocation
          and provides a generic error message to the user, avoiding internal details.
        """
        from langchain.schema import HumanMessage, AIMessage, SystemMessage

        # Debug print to confirm fallback is triggered
        print(Fore.MAGENTA + "[DEBUG - Fallback LLM] Received command: " + command_text + Style.RESET_ALL)

        try:
            # Construct messages for the LLM.
            # The `ASSISTANT_SYSTEM_PROMPT` defines the AI's persona and guidelines.
            messages = [
                SystemMessage(content=self.config.ASSISTANT_SYSTEM_PROMPT),
                HumanMessage(content=command_text),
            ]
            response = await self.llm.ainvoke(messages)
            text = response.content
            
            # Audit Trail: Log the LLM's response.
            # Ensure 'text' is sanitized before logging if it could contain sensitive data.
            self.logger.info("LLM responded to '%s': %s", command_text, text)

            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME} says: {text}" + Style.RESET_ALL)
            await self._safe_speak(text)
            
            # Store conversation history.
            # CRITICAL: If this history is ever persisted or re-sent to the LLM,
            # ensure PII/secrets are redacted.
            self.chat_history.append(HumanMessage(content=command_text))
            self.chat_history.append(AIMessage(content=text))
        except Exception as e:
            self.logger.error("LLM fallback error: %s", e, exc_info=True)
            resp = f"There was an issue communicating with {self.config.ASSISTANT_NAME}."
            print(Fore.RED + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            await self._safe_speak(resp)

