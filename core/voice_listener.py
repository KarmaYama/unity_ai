# core/voice_listener.py

import string
from colorama import Fore, Style
from core.stt import transcribe_from_push_to_talk
from core.config import Config
from core.logger_config import setup_logger  # Fallback if no logger passed

def _contains_control_chars(s: str) -> bool:
    """Return True if any character in s is not in string.printable."""
    return any(ch not in string.printable for ch in s)

async def listen_for_voice(
    voice_flag_ref: dict,
    process_command_fn,
    config: Config,
    logger=None,
):
    """
    Voice-mode loop: while voice_flag_ref['enabled'] is True,
    pressing the configured STT_PUSH_TO_TALK_KEY records/transcribes one utterance,
    calls process_command_fn. If not handled by a direct command, falls back to LLM.
    Uses the passed-in logger (or creates one if None).
    """

    # Use the provided logger or set one up now
    if logger is None:
        logger = setup_logger(config)

    key_name = config.STT_PUSH_TO_TALK_KEY.strip().lower()
    logger.info("Entering voice mode; listening for key '%s' to start.", key_name)
    print(
        Fore.MAGENTA
        + f"Ready for voice command (press and hold '{config.STT_PUSH_TO_TALK_KEY}' to start)..."
        + Style.RESET_ALL
    )

    try:
        while voice_flag_ref.get("enabled", False):
            # Wait for the user to press+hold the STT key and get a transcription
            try:
                voice_command = await transcribe_from_push_to_talk(
                    push_key=key_name,
                    config=config
                )
            except Exception as stt_err:
                logger.error("STT transcription error: %s", stt_err, exc_info=True)
                print(Fore.RED + "STT error; please try again." + Style.RESET_ALL)
                continue

            if not voice_flag_ref.get("enabled", False):
                # If voice mode was disabled during transcription, break out
                break

            if voice_command is None:
                # No speech detected (silent or low confidence). Prompt again.
                print(Fore.YELLOW + "No command detected. Press the STT key again or say 'disable voice mode'." + Style.RESET_ALL)
                continue

            voice_command = voice_command.strip()
            if not voice_command:
                # Empty string, skip
                continue

            # Reject any control characters in the recognized text
            if _contains_control_chars(voice_command):
                logger.warning("Rejected voice command with control characters: %r", voice_command)
                print(Fore.RED + "Invalid input detected in voice command. Please try again." + Style.RESET_ALL)
                continue

            logger.debug("Voice command recognized: %s", voice_command)
            print(Fore.MAGENTA + f"Voice command: {voice_command}" + Style.RESET_ALL)

            # First try to handle as a direct command
            try:
                handled = await process_command_fn(voice_command)
            except Exception as cmd_err:
                logger.error("Error while processing voice command '%s': %s", voice_command, cmd_err, exc_info=True)
                handled = False

            if not handled:
                # Attempt LLM fallback if process_command_fn belongs to CommandHandler
                bound_self = getattr(process_command_fn, "__self__", None)
                fallback_fn = getattr(bound_self, "fallback_to_llm", None)
                if fallback_fn is not None:
                    try:
                        await fallback_fn(voice_command)
                    except Exception as fb_err:
                        logger.error("LLM fallback error on '%s': %s", voice_command, fb_err, exc_info=True)
                        try:
                            await bound_self._safe_speak("Sorry, I couldn’t process that voice command fully.")
                        except Exception:
                            pass
                else:
                    logger.warning("No fallback method found for voice command: %s", voice_command)
                    try:
                        await bound_self._safe_speak("Sorry, I couldn’t process that voice command.")
                    except Exception:
                        pass

            # If voice mode is still enabled, prompt for the next action
            if voice_flag_ref.get("enabled", False):
                print(
                    Fore.MAGENTA
                    + f"Press '{config.STT_PUSH_TO_TALK_KEY}' again to listen for another command, or say 'disable voice mode' to exit."
                    + Style.RESET_ALL
                )

        # Once the loop exits (voice_flag_ref["enabled"] is False), notify user
        logger.info("Exiting voice mode; returning to text input.")
        print(Fore.MAGENTA + "Voice mode off; returning to text input." + Style.RESET_ALL)

    except Exception as loop_err:
        # Catch any unexpected exception to avoid crashing the entire assistant
        logger.error("Unexpected error in voice listener: %s", loop_err, exc_info=True)
        print(Fore.RED + "Voice listener encountered an error. Exiting voice mode." + Style.RESET_ALL)
        # Ensure voice mode is disabled
        voice_flag_ref["enabled"] = False
        try:
            bound_self = getattr(process_command_fn, "__self__", None)
            if bound_self:
                await bound_self._safe_speak("Voice mode has been disabled due to an internal error.")
        except Exception:
            pass
