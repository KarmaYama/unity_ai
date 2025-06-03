import re
from colorama import Fore, Style
from core.tts import speak # This import is fine, speak will get config internally
from core.commands.bookmark_commands import BookmarkCommands
from core.commands.system_commands import SystemCommands

class CommandHandler:
    """
    Central dispatcher for commands, delegating to specific command modules.
    Also handles voice mode toggling and LLM fallback.
    """

    def __init__(self, llm, tools, search_tool, logger, chat_history, voice_flag_ref, config):
        """
        - llm: the language model instance
        - tools: dictionary of LangChain tools (open_website, open_application, etc.)
        - search_tool: DuckDuckGo search function or None
        - logger: the logger object
        - chat_history: a list for messages to keep conversation context
        - voice_flag_ref: a dict-like with key "enabled" pointing to a bool
        - config: The Config object containing all application settings
        """
        self.llm = llm
        self.tools = tools
        self.search_tool = search_tool
        self.logger = logger
        self.chat_history = chat_history
        self.voice_flag_ref = voice_flag_ref
        self.config = config # Store the config object

        # Initialize command modules
        self.bookmark_commands = BookmarkCommands(logger=self.logger, config=self.config)
        self.system_commands = SystemCommands(
            logger=self.logger,
            config=self.config,
            tools=self.tools,
            search_tool=self.search_tool
        )

    async def _safe_speak(self, text: str):
        """Wrapper around TTS that doesn’t throw."""
        try:
            await speak(text)
        except Exception as e:
            self.logger.error(f"TTS Error: {e}", exc_info=True)

    async def process_command(self, command_text: str):
        """
        Returns True if the command was handled (including direct‐invocation or toggle).
        Otherwise returns False (means “fallback to LLM”).
        """
        self.logger.debug(f"User command: {command_text}")
        lower = command_text.lower().strip()
        parts = command_text.strip().split() # Re-split for general command parsing

        # ── Global Toggles ───────────────────────────────────────────────────
        if lower == "enable voice mode":
            self.voice_flag_ref["enabled"] = True
            print(
                Fore.YELLOW
                + f"{self.config.ASSISTANT_NAME}: Voice mode enabled. Press and hold {self.config.STT_PUSH_TO_TALK_KEY} to start listening. Press {self.config.STT_PUSH_TO_TALK_KEY} again to stop."
                + Style.RESET_ALL
            )
            await self._safe_speak(
                f"Voice mode enabled. Press and hold {self.config.STT_PUSH_TO_TALK_KEY} to start listening. Press {self.config.STT_PUSH_TO_TALK_KEY} again to stop."
            )
            return True

        if lower == "disable voice mode":
            self.voice_flag_ref["enabled"] = False
            print(
                Fore.YELLOW
                + f"{self.config.ASSISTANT_NAME}: Voice mode disabled. Returning to text input."
                + Style.RESET_ALL
            )
            await self._safe_speak("Voice mode disabled. Returning to text input.")
            return True

        # ── Delegate to Command Modules ──────────────────────────────────────
        # System Commands (open, close, weather, search)
        if await self.system_commands.handle_open_website(command_text):
            return True
        if await self.system_commands.handle_open_application(command_text):
            return True
        if await self.system_commands.handle_close_application(command_text):
            return True
        if await self.system_commands.handle_get_weather(command_text):
            return True
        if await self.system_commands.handle_search(command_text):
            return True

        # Bookmark Commands
        if len(parts) >= 2 and parts[0].lower() == "zira" and parts[1].lower() == "bookmark":
            if len(parts) > 2:
                sub_command = parts[2].lower()
                if sub_command == "add":
                    return await self.bookmark_commands.handle_add(parts)
                elif sub_command == "list":
                    return await self.bookmark_commands.handle_list(parts)
                elif sub_command == "jump":
                    return await self.bookmark_commands.handle_jump(parts)
                elif sub_command == "remove":
                    return await self.bookmark_commands.handle_remove(parts)
            else:
                await self._safe_speak("Usage: 'zira bookmark add <alias> <path>', 'zira bookmark list', 'zira bookmark jump <alias>', 'zira bookmark remove <alias>'")
            return True

        # ── Fallback: LLM ────────────────────────────────────────────────────
        return False  # indicate “not handled by direct pattern”

    async def fallback_to_llm(self, command_text: str):
        """
        Sends `command_text` to the LLM with a system prompt,
        appends to chat_history, and speaks/prints the response.
        """
        from langchain.schema import HumanMessage, AIMessage, SystemMessage
        try:
            messages = [
                SystemMessage(
                    content=self.config.ASSISTANT_SYSTEM_PROMPT # Use system prompt from config
                ),
                HumanMessage(content=command_text),
            ]
            response = await self.llm.ainvoke(messages)
            text = response.content
            print(Fore.CYAN + f"{self.config.ASSISTANT_NAME} says: {text}" + Style.RESET_ALL)
            await self._safe_speak(text)
            self.chat_history.append(HumanMessage(content=command_text))
            self.chat_history.append(AIMessage(content=text))
        except Exception as e:
            self.logger.error(f"LLM fallback error: {e}", exc_info=True)
            resp = f"There was an issue communicating with {self.config.ASSISTANT_NAME}."
            print(Fore.RED + f"{self.config.ASSISTANT_NAME}: {resp}" + Style.RESET_ALL)
            await self._safe_speak(resp)
