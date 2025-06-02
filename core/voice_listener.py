import asyncio
from colorama import Fore, Style
from core.stt import transcribe_from_push_to_talk

async def listen_for_voice(
    voice_flag_ref: dict,
    process_command_fn,
):
    """
    A toggle‐style loop: once voice_flag_ref['enabled'] is True,
    pressing Ctrl records/transcribes one utterance, calls process_command_fn,
    then prompts to press Ctrl again or disable voice mode.
    """
    print(
        Fore.MAGENTA
        + "Ready for voice command (press and hold Ctrl to start)…"
        + Style.RESET_ALL
    )
    from core.logger_config import setup_logger  # in case process_command_fn tries logging
    logger = setup_logger()

    while voice_flag_ref["enabled"]:
        voice_command = await transcribe_from_push_to_talk(push_key="ctrl")
        if voice_command:
            print(Fore.MAGENTA + f"Voice command: {voice_command}" + Style.RESET_ALL)
            await process_command_fn(voice_command)

        if voice_flag_ref["enabled"]:
            print(
                Fore.MAGENTA
                + "Press Ctrl again to listen for another command, or type 'disable voice mode' to exit."
                + Style.RESET_ALL
            )
            # No need to await speak here—process_command_fn (if disabling) will speak as needed

    # Once voice_mode is False, we fall out:
    print(Fore.MAGENTA + "Voice mode off; returning to text input." + Style.RESET_ALL)
