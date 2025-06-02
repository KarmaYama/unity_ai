# core/voice_listener.py

import asyncio
from colorama import Fore, Style
from core.stt import transcribe_from_push_to_talk
from core.config import Config # Import Config

async def listen_for_voice(
    voice_flag_ref: dict,
    process_command_fn,
    config: Config # Add the config argument here
):
    """
    A toggle‐style loop: once voice_flag_ref['enabled'] is True,
    pressing Ctrl records/transcribes one utterance, calls process_command_fn.
    If not handled by a direct command, it now falls back to the LLM.
    Then prompts to press Ctrl again or disable voice mode.
    Now accepts the Config object.
    """
    print(
        Fore.MAGENTA
        + f"Ready for voice command (press and hold '{config.STT_PUSH_TO_TALK_KEY}' to start)…"
        + Style.RESET_ALL
    )
    from core.logger_config import setup_logger  # in case process_command_fn tries logging
    logger = setup_logger(config) # Pass config to logger setup

    while voice_flag_ref["enabled"]:
        voice_command = await transcribe_from_push_to_talk(push_key=config.STT_PUSH_TO_TALK_KEY, config=config) # Pass config to STT
        if voice_command:
            print(Fore.MAGENTA + f"Voice command: {voice_command}" + Style.RESET_ALL)
            handled = await process_command_fn(voice_command)
            if not handled:
                # Fallback to LLM if the command wasn't directly handled
                from core.command_handler import CommandHandler # Import here to avoid circular dependency
                # Assuming process_command_fn is bound to a CommandHandler instance
                if isinstance(process_command_fn.__self__, CommandHandler):
                    await process_command_fn.__self__.fallback_to_llm(voice_command)
                else:
                    logger.warning("Could not access CommandHandler for LLM fallback in voice mode.")
                    await process_command_fn.__self__._safe_speak("Sorry, I couldn't process that voice command fully.")

        if voice_flag_ref["enabled"]:
            print(
                Fore.MAGENTA
                + f"Press '{config.STT_PUSH_TO_TALK_KEY}' again to listen for another command, or type 'disable voice mode' to exit."
                + Style.RESET_ALL
            )
            # No need to await speak here—fallback_to_llm or process_command_fn will handle it

    # Once voice_mode is False, we fall out:
    print(Fore.MAGENTA + "Voice mode off; returning to text input." + Style.RESET_ALL)