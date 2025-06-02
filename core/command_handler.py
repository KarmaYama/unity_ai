import re
from colorama import Fore, Style
from core.tts import speak

# Precompile regexes once:
_WEBSITE_REGEX = re.compile(r"^open\s+website\s+(https?://\S+)", re.IGNORECASE)
_APP_REGEX     = re.compile(r"^open\s+(.+)$",            re.IGNORECASE)
_CLOSE_REGEX   = re.compile(r"^close\s+(.+)$",           re.IGNORECASE)
_WEATHER_REGEX = re.compile(r"^(?:weather(?:\s+in)?\s+)(.+)$", re.IGNORECASE)
_SEARCH_REGEX  = re.compile(r"^search\s+(.+)$",           re.IGNORECASE)

class CommandHandler:
    """
    Encapsulates 'process_command' logic, including direct invocations
    (open/close/get_weather/search) and LLM fallback.
    """

    def __init__(self, llm, tools, search_tool, logger, chat_history, voice_flag_ref):
        """
        - llm: the language model instance
        - tools: list of LangChain tools (open_website, open_application, etc.)
        - search_tool: DuckDuckGo search function or None
        - logger: the logger object
        - chat_history: a list for messages to keep conversation context
        - voice_flag_ref: a dict-like with key "enabled" pointing to a bool
        """
        self.llm = llm
        self.tools = tools
        self.search_tool = search_tool
        self.logger = logger
        self.chat_history = chat_history
        self.voice_flag_ref = voice_flag_ref

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

        # Toggle voice mode:
        if lower == "enable voice mode":
            self.voice_flag_ref["enabled"] = True
            print(
                Fore.YELLOW
                + "Zira: Voice mode enabled. Press and hold Ctrl to start listening. Press Ctrl again to stop."
                + Style.RESET_ALL
            )
            await self._safe_speak(
                "Voice mode enabled. Press and hold Control to start listening. Press Control again to stop."
            )
            return True

        if lower == "disable voice mode":
            self.voice_flag_ref["enabled"] = False
            print(
                Fore.YELLOW
                + "Zira: Voice mode disabled. Returning to text input."
                + Style.RESET_ALL
            )
            await self._safe_speak("Voice mode disabled. Returning to text input.")
            return True

        # open website:
        m = _WEBSITE_REGEX.match(command_text)
        if m:
            url = m.group(1)
            self.logger.debug(f"Direct invocation: open_website('{url}')")
            try:
                resp = await self.tools["open_website"].ainvoke(url)
                self.logger.debug(f"open_website response: {resp}")
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in open_website: {e}", exc_info=True)
                resp = f"Sorry, I couldn't open the website {url}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            return True

        # open application:
        m = _APP_REGEX.match(command_text)
        if m:
            app_name = m.group(1).strip()
            self.logger.debug(f"Direct invocation: open_application('{app_name}')")
            try:
                resp = await self.tools["open_application"].ainvoke(app_name)
                self.logger.debug(f"open_application response: {resp}")
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in open_application: {e}", exc_info=True)
                resp = f"Sorry, I couldn't open the application {app_name}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            return True

        # close application:
        m = _CLOSE_REGEX.match(command_text)
        if m:
            app_to_close = m.group(1).strip()
            self.logger.debug(f"Direct invocation: close_application('{app_to_close}')")
            try:
                resp = await self.tools["close_application"].ainvoke(app_to_close)
                self.logger.debug(f"close_application response: {resp}")
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in close_application: {e}", exc_info=True)
                resp = f"Sorry, I couldn't close the application {app_to_close}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            return True

        # get weather (placeholder):
        m = _WEATHER_REGEX.match(command_text)
        if m:
            location = m.group(1).strip()
            self.logger.debug(f"Direct invocation: get_weather('{location}')")
            try:
                resp = await self.tools["get_weather"].ainvoke(location)
                self.logger.debug(f"get_weather response: {resp}")
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            except Exception as e:
                self.logger.error(f"Error in get_weather: {e}", exc_info=True)
                resp = f"Sorry, I couldn't retrieve weather for {location}."
                await self._safe_speak(resp)
                print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            return True

        # search:
        m = _SEARCH_REGEX.match(command_text)
        if m:
            query = m.group(1).strip()
            if self.search_tool:
                self.logger.debug(f"Direct invocation: DuckDuckGo Search('{query}')")
                try:
                    results = await self.search_tool(query)
                    self.logger.debug(f"DuckDuckGo Search response: {results}")
                    print(Fore.CYAN + f"Zira: {results}" + Style.RESET_ALL)
                    await self._safe_speak(results)
                except Exception as e:
                    self.logger.error(f"Error in DuckDuckGo Search: {e}", exc_info=True)
                    resp = "Sorry, I couldn't perform the search."
                    await self._safe_speak(resp)
                    print(Fore.CYAN + f"Zira: {resp}" + Style.RESET_ALL)
            else:
                resp = "The search tool is not available."
                await self._safe_speak(resp)
                print(Fore.YELLOW + f"Zira: {resp}" + Style.RESET_ALL)
            return True

        # Fallback: LLM
        return False  # indicate “not handled by direct pattern”


    async def fallback_to_llm(self, command_text: str):
        """
        Sends `command_text` to the LLM with a system prompt,
        appends to chat_history, and speaks/prints the response.
        """
        from core.tts import speak  # safe_speak already imported
        from langchain.schema import HumanMessage, AIMessage, SystemMessage
        try:
            messages = [
                SystemMessage(
                    content=(
                        "You are Zira, a highly sophisticated and intelligent AI. You engage "
                        "in conversations naturally, providing thoughtful and intelligent responses. You have a "
                        "subtle wit and avoid robotic language. Strive for eloquence and depth."
                    )
                ),
                HumanMessage(content=command_text),
            ]
            response = await self.llm.ainvoke(messages)
            text = response.content
            print(Fore.CYAN + f"Zira says: {text}" + Style.RESET_ALL)
            await self._safe_speak(text)
            self.chat_history.append(HumanMessage(content=command_text))
            self.chat_history.append(AIMessage(content=text))
        except Exception as e:
            self.logger.error(f"LLM fallback error: {e}", exc_info=True)
            resp = "There was an issue communicating with Zira."
            print(Fore.RED + f"Zira: {resp}" + Style.RESET_ALL)
            await self._safe_speak(resp)
