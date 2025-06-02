import asyncio
import os
import logging
import re
from datetime import datetime
from colorama import Fore, Style
import keyboard  # For detecting alt key press

from core.config import load_api_key, init_llm
from core.tts import speak
from core.stt import transcribe_from_push_to_talk
from tools.system_tools import open_application, open_website, get_weather
from tools.agent_tools import setup_tools

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# ----------------------------------------
# Setup a timestamped logger for each session
# ----------------------------------------

# Create log directory if not exists
log_dir = "log"
os.makedirs(log_dir, exist_ok=True)

# Dynamic file name with timestamp
log_filename = os.path.join(log_dir, f"zira_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logger = logging.getLogger("zira_logger")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# ----------------------------------------
# Regex patterns for direct tool‐invocation
# ----------------------------------------
_WEBSITE_REGEX = re.compile(r"^open\s+website\s+(https?://\S+)", re.IGNORECASE)
_APP_REGEX = re.compile(r"^open\s+(.+)$", re.IGNORECASE)
_WEATHER_REGEX = re.compile(r"^(?:weather(?:\s+in)?\s+)(.+)$", re.IGNORECASE)
_SEARCH_REGEX = re.compile(r"^search\s+(.+)$", re.IGNORECASE)

async def safe_speak(text: str):
    try:
        await speak(text)
    except Exception as tts_error:
        logger.error(f"TTS Error: {tts_error}", exc_info=True)

async def main():
    api_key = load_api_key()
    llm = init_llm(api_key)
    tools = setup_tools(api_key, llm)
    search_tool = None
    for tool in tools:
        if tool.name == "DuckDuckGo Search":
            search_tool = tool.func
            break

    voice_mode_enabled = False

    print(Fore.GREEN + "Zira is ready. Type 'enable voice mode' to use voice, or type your command:")
    await safe_speak("Hello, I am Zira. Type 'enable voice mode' to use voice commands, or type your command.")

    chat_history = []

    async def process_command(command_text: str):
        nonlocal voice_mode_enabled
        logger.debug(f"User command: {command_text}")

        if command_text.lower() == "enable voice mode":
            voice_mode_enabled = True
            print(Fore.YELLOW + "Zira: Voice mode enabled. Press and hold Alt to speak." + Style.RESET_ALL)
            await safe_speak("Voice mode enabled. Press and hold Alt to speak.")
            return True
        elif command_text.lower() == "disable voice mode":
            voice_mode_enabled = False
            print(Fore.YELLOW + "Zira: Voice mode disabled. Returning to text input." + Style.RESET_ALL)
            await safe_speak("Voice mode disabled. Returning to text input.")
            return True

        website_match = _WEBSITE_REGEX.match(command_text)
        if website_match:
            url = website_match.group(1)
            logger.debug(f"Direct invocation: open_website('{url}')")
            try:
                response_text = await open_website.ainvoke(url)
                logger.debug(f"open_website response: {response_text}")
                print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            except Exception as e:
                logger.error(f"Error in open_website('{url}'): {e}", exc_info=True)
                response_text = f"Sorry, I couldn't open the website {url}."
                await safe_speak(response_text)
                print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            return True

        app_match = _APP_REGEX.match(command_text)
        if app_match:
            app_name = app_match.group(1).strip()
            logger.debug(f"Direct invocation: open_application('{app_name}')")
            try:
                response_text = await open_application.ainvoke(app_name)
                logger.debug(f"open_application response: {response_text}")
                print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            except Exception as e:
                logger.error(f"Error in open_application('{app_name}'): {e}", exc_info=True)
                response_text = f"Sorry, I couldn't open the application {app_name}."
                await safe_speak(response_text)
                print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            return True

        weather_match = _WEATHER_REGEX.match(command_text)
        if weather_match:
            location = weather_match.group(1).strip()
            logger.debug(f"Direct invocation: get_weather('{location}')")
            try:
                response_text = await get_weather.ainvoke(location)
                logger.debug(f"get_weather response: {response_text}")
                print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            except Exception as e:
                logger.error(f"Error in get_weather('{location}'): {e}", exc_info=True)
                response_text = f"Sorry, I couldn't retrieve weather for {location}."
                await safe_speak(response_text)
                print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            return True

        search_match = _SEARCH_REGEX.match(command_text)
        if search_match:
            query = search_match.group(1).strip()
            if search_tool:
                logger.debug(f"Direct invocation: DuckDuckGo Search('{query}')")
                try:
                    search_results = await search_tool(query)
                    logger.debug(f"DuckDuckGo Search response: {search_results}")
                    print(Fore.CYAN + f"Zira: {search_results}" + Style.RESET_ALL)
                    await safe_speak(search_results)
                except Exception as e:
                    logger.error(f"Error during DuckDuckGo Search('{query}'): {e}", exc_info=True)
                    response_text = f"Sorry, I couldn't perform the search."
                    await safe_speak(response_text)
                    print(Fore.CYAN + f"Zira: {response_text}" + Style.RESET_ALL)
            else:
                await safe_speak("The search tool is not available.")
                print(Fore.YELLOW + "Zira: The search tool is not available." + Style.RESET_ALL)
            return True

        try:
            messages = [
                SystemMessage(content="You are Zira, a highly sophisticated and intelligent AI. You engage in conversations with a human in a way that feels natural and insightful, much like a very knowledgeable human companion. Your responses are articulate, thoughtful, and demonstrate a deep understanding of the topic at hand. While you are helpful, your primary mode is conversational, aiming for a human-like exchange rather than simply acting as an assistant who only answers questions directly. You possess a subtle wit and can weave in relevant insights or perspectives to enrich the conversation. Avoid overly simplistic or robotic language. Strive for eloquence and depth in your interactions."),
                HumanMessage(content=command_text)
            ]
            response = await llm.ainvoke(messages)
            print(Fore.CYAN + f"Zira says: {response.content}" + Style.RESET_ALL)
            await safe_speak(response.content)
            chat_history.append(HumanMessage(content=command_text))
            chat_history.append(AIMessage(content=response.content))
            return True
        except Exception as e:
            logger.error(f"Error during LLM invocation (fallback): {e}", exc_info=True)
            print(Fore.RED + f"Error with Zira (fallback): {e}" + Style.RESET_ALL)
            await safe_speak("There was an issue communicating with Zira.")
            return True
        return False

    async def listen_for_voice():
        while True:
            if voice_mode_enabled and keyboard.is_pressed('alt'):
                print(Fore.MAGENTA + "Listening for voice command..." + Style.RESET_ALL)
                await safe_speak("Listening.")
                voice_command = await transcribe_from_push_to_talk()
                if voice_command:
                    print(Fore.MAGENTA + f"Voice command: {voice_command}" + Style.RESET_ALL)
                    await process_command(voice_command)
                    # Briefly pause to avoid rapid re-triggering
                    await asyncio.sleep(0.3)
            await asyncio.sleep(0.1)

    # Start listening for voice in the background
    asyncio.create_task(listen_for_voice())

    while True:
        try:
            command = input(Fore.WHITE + "You> " + Style.RESET_ALL).strip()
            if not command:
                continue

            if command.lower() in ["exit", "quit", "goodbye"]:
                await safe_speak("Goodbye.")
                print(Fore.GREEN + "Zira: Goodbye!" + Style.RESET_ALL)
                break

            await process_command(command)

        except KeyboardInterrupt:
            await safe_speak("Session terminated. Goodbye.")
            print(Fore.GREEN + "\nZira: Session terminated by user." + Style.RESET_ALL)
            break

        except Exception as e:
            logger.error(f"Error during main loop: {e}", exc_info=True)
            error_msg = "Zira: Sorry, something went wrong in the main loop."
            print(Fore.RED + error_msg + Style.RESET_ALL)
            await safe_speak("Sorry, something went wrong.")

    logger.debug("Session ended.")
    logger.handlers.clear()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error during Zira startup or execution: {e}", exc_info=True)
        print(Fore.RED + f"Fatal error: {e}" + Style.RESET_ALL)
    finally:
        print(Fore.RESET + "Exiting Zira." + Style.RESET_ALL)