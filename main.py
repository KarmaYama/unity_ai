import asyncio
import os
import re
from colorama import Fore, Style

from core.config import load_api_key, init_llm
from core.logger_config import setup_logger
from core.command_handler import CommandHandler
from core.voice_listener import listen_for_voice
from core.tts import speak
from tools.system_tools import (
    open_application,
    open_website,
    get_weather,
    close_application,
)
from tools.agent_tools import setup_tools

# ----------------------------------------
# Bootstrap logger
# ----------------------------------------
logger = setup_logger("zira_logger")

# ----------------------------------------
# Main entrypoint
# ----------------------------------------
async def main():
    api_key = load_api_key()
    llm = init_llm(api_key)
    tools = setup_tools(api_key, llm)

    # Extract search if available
    search_tool = None
    for t in tools:
        if t.name == "DuckDuckGo Search":
            search_tool = t.func
            break

    # A shared flag dict so CommandHandler can toggle voice mode.
    voice_flag = {"enabled": False}
    chat_history = []

    # Map tool names to their functions (for convenience inside CommandHandler)
    tool_map = {
        "open_application": open_application,
        "open_website": open_website,
        "get_weather": get_weather,
        "close_application": close_application,
    }

    handler = CommandHandler(
        llm=llm,
        tools=tool_map,
        search_tool=search_tool,
        logger=logger,
        chat_history=chat_history,
        voice_flag_ref=voice_flag,
    )

    print(
        Fore.GREEN
        + "Zira is ready. Type 'enable voice mode' to use voice, or type your command:"
        + Style.RESET_ALL
    )
    try:
        await handler._safe_speak(
            "Hello, I am Zira. Type 'enable voice mode' to use voice commands, or type your command."
        )
    except Exception:
        pass  # ignore if TTS fails

    # Main REPL loop:
    while True:
        command = input(Fore.WHITE + "You> " + Style.RESET_ALL).strip()
        if not command:
            continue

        low = command.lower()
        if low in ["exit", "quit", "goodbye"]:
            bye = "Goodbye!"
            print(Fore.GREEN + f"Zira: {bye}" + Style.RESET_ALL)
            await handler._safe_speak(bye)
            break

        handled = await handler.process_command(command)
        if not handled:
            # If direct patterns didn’t match, fall back to LLM
            await handler.fallback_to_llm(command)

        # If voice mode was just enabled, hand off to voice_listener
        if voice_flag["enabled"]:
            await listen_for_voice(
                voice_flag_ref=voice_flag,
                process_command_fn=handler.process_command,
            )

    logger.debug("Session ended.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # If user hits Ctrl+C during main, say goodbye
        asyncio.run(speak("Session terminated. Goodbye."))
    except Exception as e:
        logger.error(f"Fatal error during Zira startup or execution: {e}", exc_info=True)
        print(Fore.RED + f"Fatal error: {e}" + Style.RESET_ALL)
    finally:
        print(Fore.RESET + "Exiting Zira." + Style.RESET_ALL)
