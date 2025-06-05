# core/voice_listener.py

import string
import asyncio
from colorama import Fore, Style
from core.stt import transcribe_from_push_to_talk
from core.logger_config import setup_logger  # To obtain a shared logger
from core.tts import speak # Import speak function

def _contains_control_chars(s: str) -> bool:
    """Return True if any character in s is not in string.printable."""
    return any(ch not in string.printable for ch in s)


async def listen_for_voice(
    voice_flag_ref: dict,
    process_command_fn,
    config,
    logger=None,
):
    """
    Voice-mode loop: while voice_flag_ref['enabled'] is True,
    pressing the configured STT_PUSH_TO_TALK_KEY records/transcribes one utterance,
    calls process_command_fn. If not handled by a direct command, falls back to LLM.
    Uses the passed-in logger (or creates one if None).
    """

    # Acquire—or create—our shared logger
    if logger is None:
        logger = setup_logger(config, name="voice_listener")

    key_name = config.STT_PUSH_TO_TALK_KEY.strip().lower()
    logger.info("Entering voice mode; listening for key '%s'.", key_name)
    print(
        Fore.MAGENTA
        + f"Voice mode active. Press and hold '{config.STT_PUSH_TO_TALK_KEY}' to speak."
        + Style.RESET_ALL
    )

    try:
        while voice_flag_ref.get("enabled", False):
            # 1) Block until user presses the STT key and we get a transcription
            try:
                voice_command = await transcribe_from_push_to_talk(config=config, logger=logger)
            except KeyboardInterrupt:
                # Allow Ctrl+C to exit voice mode immediately
                logger.info("KeyboardInterrupt detected. Exiting voice mode.")
                voice_flag_ref["enabled"] = False
                break
            except Exception as stt_err:
                logger.error("STT transcription error: %s", stt_err, exc_info=True)
                print(Fore.RED + "STT error; please try again." + Style.RESET_ALL)
                # Brief pause to avoid a tight retry loop
                await asyncio.sleep(0.1)
                continue

            # If voice mode was disabled during transcription, break out
            if not voice_flag_ref.get("enabled", False):
                break

            # 2) Handle no‐speech or empty
            if voice_command is None:
                print(
                    Fore.YELLOW
                    + "No command detected. Press the STT key again or say 'disable voice mode'."
                    + Style.RESET_ALL
                )
                continue

            voice_command = voice_command.strip()
            if not voice_command:
                # Empty string, skip without logging
                continue

            # 3) Reject control characters
            if _contains_control_chars(voice_command):
                logger.warning("Rejected voice command containing control chars: %r", voice_command)
                print(
                    Fore.RED
                    + "Invalid input detected in voice command. Please try again."
                    + Style.RESET_ALL
                )
                continue

            logger.debug("Voice command recognized: %s", voice_command)
            print(Fore.MAGENTA + f"Voice command: {voice_command}" + Style.RESET_ALL)

            # 4) First attempt direct command handling
            try:
                # process_command_fn (CommandDispatcher.process_command)
                # will handle system commands first, then fallback to LLM.
                await process_command_fn(voice_command) 
            except Exception as cmd_err:
                logger.error(
                    "Error while processing voice command '%s': %s",
                    voice_command,
                    cmd_err,
                    exc_info=True
                )
                print(Fore.RED + "Error processing voice command; please try again." + Style.RESET_ALL)
                # No need to call a fallback_fn or _safe_speak explicitly here,
                # as dispatcher.process_command will handle LLM fallback and TTS.
                await speak("Sorry, I encountered an error processing that command.")
                continue

            # 5) If still in voice mode, prompt for next action
            if voice_flag_ref.get("enabled", False):
                print(
                    Fore.MAGENTA
                    + f"Press '{config.STT_PUSH_TO_TALK_KEY}' again to listen, or say 'disable voice mode' to exit."
                    + Style.RESET_ALL
                )

        # Exit message once voice mode is turned off
        logger.info("Voice mode disabled; returning to text input.")
        print(Fore.MAGENTA + "Voice mode off; returning to text input." + Style.RESET_ALL)

    except Exception as loop_err:
        # Catch any unexpected exception to avoid crashing the entire assistant
        logger.error("Unexpected error in voice listener: %s", loop_err, exc_info=True)
        print(Fore.RED + "Voice listener encountered an error. Exiting voice mode." + Style.RESET_ALL)
        voice_flag_ref["enabled"] = False
        # Try notifying via TTS
        await speak("Voice mode has been disabled due to an internal error.")

