#main.py

import asyncio
from colorama import Fore, Style

# Import the new Config class
from core.config import Config
from core.logger_config import setup_logger
from core.command_handler import CommandHandler
from core.voice_listener import listen_for_voice
from core.tts import speak # Keep speak for direct usage in main for initial greeting
from tools.system_tools import (
    open_application,
    open_website,
    get_weather,
    close_application,
)
from tools.agent_tools import setup_tools

# ----------------------------------------
# Initialize Configuration
# ----------------------------------------
config = Config()

# ----------------------------------------
# Bootstrap logger
# ----------------------------------------
# Pass the config object to setup_logger
logger = setup_logger(config)

# ----------------------------------------
# Main entrypoint
# ----------------------------------------
async def main():
    # Load LLM using the config object
    llm = config.init_llm()
    # Pass the config object to setup_tools
    tools = setup_tools(config, llm)

    # Extract search if available
    search_tool = None
    for t in tools:
        # Note: The tool name "DuckDuckGo Search" is hardcoded here.
        # If you wanted to make this configurable, you'd add it to .env
        # and retrieve it from config.
        if t.name == "DuckDuckGo Search":
            search_tool = t.func
            break

    # A shared flag dict so CommandHandler can toggle voice mode.
    voice_flag = {"enabled": False}
    chat_history = []

    # Map tool names to their functions (for convenience inside CommandHandler)
    # These are still hardcoded as they represent the internal mapping of available tools.
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
        config=config # Pass the config object to CommandHandler
    )

    print(
        Fore.GREEN
        + f"{config.ASSISTANT_NAME} is ready. Type 'enable voice mode' to use voice, or type your command:"
        + Style.RESET_ALL
    )
    try:
        # Use the greeting from config
        await handler._safe_speak(config.ASSISTANT_GREETING)
    except Exception:
        pass  # ignore if TTS fails

    # Main REPL loop:
    while True:
        command = input(Fore.WHITE + "You> " + Style.RESET_ALL).strip()
        if not command:
            continue

        low = command.lower()
        if low in ["exit", "quit", "goodbye"]:
            bye = config.ASSISTANT_FAREWELL # Use farewell from config
            print(Fore.GREEN + f"{config.ASSISTANT_NAME}: {bye}" + Style.RESET_ALL)
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
                config=config # Pass config to voice_listener
            )

    logger.debug("Session ended.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # If user hits Ctrl+C during main, say goodbye
        # Use farewell from config
        asyncio.run(speak(f"Session terminated. {config.ASSISTANT_FAREWELL}"))
    except Exception as e:
        logger.error(f"Fatal error during {config.ASSISTANT_NAME} startup or execution: {e}", exc_info=True)
        print(Fore.RED + f"Fatal error: {e}" + Style.RESET_ALL)
    finally:
        # Use assistant name from config
        print(Fore.RESET + f"Exiting {config.ASSISTANT_NAME}." + Style.RESET_ALL)
