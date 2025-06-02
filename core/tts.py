# core/tts.py

import asyncio
import subprocess
import os
import re
import pyttsx3
from colorama import Fore

def _sanitize_text(text: str) -> str:
    """
    Remove or adjust symbols so that the TTS engine doesn't read them literally.
    - Strip out asterisks (*).
    - Convert "1:" "2:" etc. into "1." "2." so the engine will pause naturally.
    - Remove common Unicode emojis (e.g., 😊, ✨) so they are not spoken.
    """
    # 1. Remove asterisks
    sanitized = text.replace("*", "")

    # 2. Convert "number:" at the start of a line (or after whitespace) into "number."
    #    e.g. "1: Item" -> "1. Item"
    sanitized = re.sub(r"(?m)(\d+):", r"\1.", sanitized)

    # 3. Remove emojis (ranges include emoticons, symbols, flags, dingbats, etc.)
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
    sanitized = emoji_pattern.sub(r"", sanitized)

    return sanitized

async def speak(text: str):
    """
    Converts text to speech using Edge-TTS, with pyttsx3 as a fallback.
    Before speaking, sanitize the text so symbols like '*', '1:', or emojis won't be spoken literally.
    """
    # First, sanitize punctuation, list markers, and emojis
    safe_text = _sanitize_text(text)

    try:
        import edge_tts

        # Choose a voice (e.g., "en-US-JennyNeural")
        voice_name = "en-US-JennyNeural"
        communicate = edge_tts.Communicate(safe_text, voice_name)

        temp_audio_file = "temp_speech.mp3"
        await communicate.save(temp_audio_file)

        # Play via ffplay (FFmpeg). -nodisp hides video window, -autoexit closes when done.
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", temp_audio_file],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Clean up temporary file
        os.remove(temp_audio_file)

    except ImportError:
        print(
            Fore.RED
            + "Edge-TTS library not found. Please install it using 'pip install Edge-TTS'."
        )
        print(Fore.YELLOW + "Falling back to pyttsx3 for TTS.")
        _speak_pyttsx3_fallback(safe_text)

    except FileNotFoundError:
        print(
            Fore.RED
            + "ffplay (part of FFmpeg) not found. Please install FFmpeg and ensure ffplay is in your PATH."
        )
        print(Fore.YELLOW + "Falling back to pyttsx3 for audio playback.")
        _speak_pyttsx3_fallback(safe_text)

    except Exception as e:
        print(Fore.RED + f"An unexpected error occurred during Edge-TTS playback: {e}")
        print(Fore.YELLOW + "Falling back to pyttsx3 for TTS.")
        _speak_pyttsx3_fallback(safe_text)

def _speak_pyttsx3_fallback(text: str):
    """
    Fallback function for TTS using pyttsx3.
    The input text is assumed to have been sanitized already.
    """
    try:
        engine = pyttsx3.init("sapi5")  # On Windows, this often yields better voices
        voices = engine.getProperty("voices")

        # Attempt to find a Microsoft voice (Edge, Zira, David)
        selected_voice = None
        for voice in voices:
            if "Microsoft Edge" in voice.name or "Zira" in voice.name or "David" in voice.name:
                selected_voice = voice.id
                break

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
