# core/tts.py

import asyncio
import subprocess
import os
import re
import pyttsx3
import uuid
from colorama import Fore
from core.config import Config # Import Config to get settings

try:
    import edge_tts
except ImportError:
    edge_tts = None

# Global config instance (will be passed to speak)
# For this module, we'll assume it's passed into the speak function.

def _sanitize_text(text: str) -> str:
    """
    Remove or adjust symbols so that the TTS engine doesn't read them literally.
    - Strip out asterisks (*).
    - Convert "1:" "2:" etc. into "1." "2." so the engine will pause naturally.
    - Remove common Unicode emojis so they are not spoken.
    """
    sanitized = text.replace("*", "")
    sanitized = re.sub(r"(?m)(\d+):", r"\1.", sanitized)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\u2600-\u26FF"          # miscellaneous symbols
        "\u2700-\u27BF"          # dingbats
        "]+",
        flags=re.UNICODE
    )
    sanitized = emoji_pattern.sub("", sanitized)
    return sanitized


async def speak(text: str):
    """
    Converts text to speech using Edge-TTS, with pyttsx3 as a fallback.
    Uses a unique temporary file for each speech output to avoid file access conflicts.
    Ensures that we wait for the entire ffplay playback to finish before returning.
    This function now internally creates a Config instance to get settings.
    """
    # Create a local config instance to get settings
    config = Config()

    safe_text = _sanitize_text(text)

    # If Edge-TTS isn’t installed or if config dictates pyttsx3, we skip directly to pyttsx3 fallback.
    if edge_tts is None or config.TTS_ENGINE.lower() == 'pyttsx3':
        _speak_pyttsx3_fallback(safe_text, config.TTS_PYTTSX3_VOICES)
        return

    # Create a unique temp filename, so multiple calls don't collide.
    temp_audio_file = f"temp_speech_{uuid.uuid4()}.mp3"

    try:
        # Generate speech to the temp file using configured voice
        voice_name = config.TTS_EDGE_VOICE_NAME
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
        print(Fore.YELLOW + "Falling back to pyttsx3 for audio playback.")
        _speak_pyttsx3_fallback(safe_text, config.TTS_PYTTSX3_VOICES)

    except Exception as e:
        # Any other error in Edge-TTS or playback
        print(Fore.RED + f"An unexpected error occurred during Edge-TTS playback: {e}")
        print(Fore.YELLOW + "Falling back to pyttsx3 for TTS.")
        _speak_pyttsx3_fallback(safe_text, config.TTS_PYTTSX3_VOICES)

    finally:
        # Attempt to remove the temp file. If it’s still locked, we catch and warn.
        try:
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
        except OSError as e:
            print(Fore.YELLOW + f"Warning: Could not remove temporary TTS file {temp_audio_file}: {e}")


def _speak_pyttsx3_fallback(text: str, preferred_voices: list):
    """
    Fallback function for TTS using pyttsx3.
    The input text is assumed to have been sanitized already.
    Now accepts a list of preferred voice names.
    """
    try:
        engine = pyttsx3.init("sapi5")
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
        print(Fore.RED + f"Error in pyttsx3 TTS fallback: {e}")
        print(
            Fore.RED
            + "Please ensure pyttsx3 is correctly installed and configured with a TTS engine."
        )
