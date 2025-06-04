# main.py

import asyncio
import string
from colorama import Fore, Style

from core.config import Config
from core.logger_config import setup_logger
from core.command_handler import CommandHandler
from core.voice_listener import listen_for_voice
from core.tts import speak, set_tts_config
from tools.system_tools import (
    open_application,
    open_website,
    get_weather,
    close_application,
)
from tools.agent_tools import setup_tools

# ------------------------------------------------
# Note: For production, run this process under a
# non-privileged user (e.g., 'zira_user'), not root.
# ------------------------------------------------

# ----------------------------------------
# Initialize Configuration (fail-fast if missing)
# ----------------------------------------
try:
    config = Config()
except Exception as e:
    print(Fore.RED + f"Configuration error: {e}" + Style.RESET_ALL)
    exit(1)

set_tts_config(config)

# ----------------------------------------
# Bootstrap logger
# ----------------------------------------
# Pass the config object so we create ONE timestamped log per session
logger = setup_logger(config)

# ----------------------------------------
# Reject non-printable/control characters
# ----------------------------------------
def contains_control_chars(s: str) -> bool:
    return any(ch not in string.printable for ch in s)


# ----------------------------------------
# Main entrypoint
# ----------------------------------------
async def main():
    # FIXME: This uses a static GOOGLE_API_KEY. In production,
    # integrate a vault or key-rotation mechanism to fetch short-lived tokens.
    llm = config.init_llm()

    # Pass both config and logger, so FAISS/index messages go to the same log
    tools = setup_tools(config, llm, logger=logger)

    # Extract DuckDuckGo search if available
    search_tool = None
    for t in tools:
        if t.name == "DuckDuckGo Search":
            search_tool = t.func
            break

    # Shared flag to toggle voice mode
    voice_flag = {"enabled": False}
    chat_history = []

    # Whitelist of system tools
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
        config=config,
    )

    print(
        Fore.GREEN
        + f"{config.ASSISTANT_NAME} is ready. Type 'enable voice mode' to use voice, or type your command:"
        + Style.RESET_ALL
    )
    try:
        await handler._safe_speak(config.ASSISTANT_GREETING)
    except Exception:
        pass  # If TTS fails at startup, ignore

    # Main REPL loop
    while True:
        command = input(Fore.WHITE + "You> " + Style.RESET_ALL).strip()

        # Reject empty or control-character–heavy input
        if not command or contains_control_chars(command):
            print(Fore.RED + "Invalid input detected—please use standard characters only." + Style.RESET_ALL)
            continue

        low = command.lower()
        if low in ["exit", "quit", "goodbye"]:
            bye = config.ASSISTANT_FAREWELL
            print(Fore.GREEN + f"{config.ASSISTANT_NAME}: {bye}" + Style.RESET_ALL)
            await handler._safe_speak(bye)
            break

        # Try direct command handling first
        handled = await handler.process_command(command)
        if not handled:
            # If not handled, scrub if needed, then send to LLM fallback
            # (you may later insert scrub_sensitive(...) here)
            await handler.fallback_to_llm(command)

        # If voice mode was enabled, switch into voice listener
        if voice_flag["enabled"]:
            await listen_for_voice(
                voice_flag_ref=voice_flag,
                process_command_fn=handler.process_command,
                config=config,
                logger=logger,
            )

    logger.debug("Session ended.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # If user hits Ctrl+C, speak a quick farewell
        asyncio.run(speak(f"Session terminated. {config.ASSISTANT_FAREWELL}"))
    except Exception as e:
        # Fail-secure: log full details, but print a generic message to console
        logger.error("Fatal error during %s execution: %s", config.ASSISTANT_NAME, e, exc_info=True)
        print(Fore.RED + "An internal error occurred—please check the log for details." + Style.RESET_ALL)
    finally:
        print(Fore.RESET + f"Exiting {config.ASSISTANT_NAME}." + Style.RESET_ALL)
