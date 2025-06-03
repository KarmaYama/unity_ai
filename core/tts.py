import asyncio
import subprocess
import os
import re
import pyttsx3
import uuid
from colorama import Fore, Style
from core.config import Config # Import Config to get settings

try:
    import edge_tts
except ImportError:
    edge_tts = None

# Global config instance (will be passed to speak)
_config = None # This will be set by set_tts_config from main.py

def set_tts_config(config_instance: Config):
    """Sets the global config instance for the TTS module."""
    global _config
    _config = config_instance

def _sanitize_text(text: str) -> str:
    """
    Sanitizes text to improve TTS pronunciation by removing symbols and emoticons.
    - Removes common symbols.
    - Removes common emoticons.
    - Handles multiple spaces and newlines.
    """
    # Define a set of characters to be removed
    # This includes backslashes, hashes, at symbols, ampersands, percentages,
    # dollar signs, asterisks, plus signs, equals, angle brackets, slashes,
    # pipes, tildes, carets, backticks, square brackets, and curly braces.
    symbols_to_remove_pattern = re.compile(r'[\\#@&%$*+=<>/|~^`\[\]{}]+')
    sanitized = symbols_to_remove_pattern.sub("", text)

    # Convert "1:" "2:" etc. into "1." "2." so the engine will pause naturally.
    sanitized = re.sub(r"(?m)(\d+):", r"\1.", sanitized)

    # Remove common Unicode emojis and emoticons
    # This pattern covers a broad range of graphical emojis.
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\u2600-\u26FF"          # miscellaneous symbols
        "\u2700-\u27BF"          # dingbats
        "\U00002500-\U00002BEF"  # Chinese / Japanese chars
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        "]+",
        flags=re.UNICODE
    )
    sanitized = emoji_pattern.sub("", sanitized)

    # Also remove common text-based emoticons that might not be caught by Unicode pattern
    text_emoticons_to_remove = {
        ':)', ':-D', ':D', ':(', ':-(', ';)', ':P', ':-P', ':O', ':-O', '<3', 'xD',
        ':|', ':-|', ':*', ':-*', ':/', ':-/', ':\\', ':-\\'
    }
    for emo in text_emoticons_to_remove:
        sanitized = sanitized.replace(emo, "")

    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    return sanitized


async def speak(text: str):
    """
    Converts text to speech using Edge-TTS, with pyttsx3 as a fallback.
    Uses a unique temporary file for each speech output to avoid file access conflicts.
    Ensures that we wait for the entire ffplay playback to finish before returning.
    This function now uses the global _config instance set by set_tts_config.
    """
    if not _config:
        print(Fore.RED + "TTS config not set. Cannot speak. Ensure set_tts_config() is called in main.py." + Style.RESET_ALL)
        return

    safe_text = _sanitize_text(text)

    # If Edge-TTS isn’t installed or if config dictates pyttsx3, we skip directly to pyttsx3 fallback.
    if edge_tts is None or _config.TTS_ENGINE.lower() == 'pyttsx3':
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)
        return

    # Create a unique temp filename, so multiple calls don't collide.
    temp_audio_file = f"temp_speech_{uuid.uuid4()}.mp3"

    try:
        # Generate speech to the temp file using configured voice
        voice_name = _config.TTS_EDGE_VOICE_NAME
        communicate = edge_tts.Communicate(safe_text, voice_name)
        await communicate.save(temp_audio_file)

        # Play via ffplay (FFmpeg).  -nodisp hides video window, -autoexit closes when done.
        # We await the subprocess so we don’t overlap calls.
        process = await asyncio.create_subprocess_exec(
            "ffplay",
            "-nodisp",
            "-autoexit",
            temp_audio_file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await process.wait()

    except FileNotFoundError:
        # Happens if ffplay isn't found in PATH
        print(
            Fore.RED
            + "ffplay (part of FFmpeg) not found. Please install FFmpeg and ensure ffplay is in your PATH."
        )
        print(Fore.YELLOW + "Falling back to pyttsx3 for audio playback." + Style.RESET_ALL)
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)

    except Exception as e:
        # Any other error in Edge-TTS or playback
        print(Fore.RED + f"An unexpected error occurred during Edge-TTS playback: {e}" + Style.RESET_ALL)
        print(Fore.YELLOW + "Falling back to pyttsx3 for TTS." + Style.RESET_ALL)
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)

    finally:
        # Attempt to remove the temp file. If it’s still locked, we catch and warn.
        try:
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
        except OSError as e:
            print(Fore.YELLOW + f"Warning: Could not remove temporary TTS file {temp_audio_file}: {e}" + Style.RESET_ALL)


def _speak_pyttsx3_fallback(text: str, preferred_voices: list):
    """
    Fallback function for TTS using pyttsx3.
    The input text is assumed to have been sanitized already.
    Now accepts a list of preferred voice names.
    """
    try:
        engine = pyttsx3.init("sapi5") # 'sapi5' for Windows, 'nsss' for macOS, 'espeak' for Linux
        voices = engine.getProperty("voices")
        selected_voice = None
        for voice in voices:
            # Check if any preferred voice name is a substring of the voice's full name
            for preferred in preferred_voices:
                if preferred.lower() in voice.name.lower():
                    selected_voice = voice.id
                    break
            if selected_voice:
                break # Found a preferred voice, exit outer loop

        if selected_voice:
            engine.setProperty("voice", selected_voice)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(Fore.RED + f"Error in pyttsx3 TTS fallback: {e}" + Style.RESET_ALL)
        print(
            Fore.RED
            + "Please ensure pyttsx3 is correctly installed and configured with a TTS engine."
            + Style.RESET_ALL
        )
