# core/tts.py

import asyncio
import os
import re
import tempfile
import uuid
import stat
import logging
import pyttsx3
from colorama import Fore, Style
from core.config import Config

try:
    import edge_tts
except ImportError:
    edge_tts = None

# Global config instance (will be set by set_tts_config from main.py)
_config = None

def _get_logger() -> logging.Logger:
    """
    Attempt to grab the shared logger from the application.
    Falls back to root logger if setup_logger is not yet configured.
    """
    try:
        from core.logger_config import setup_logger
        cfg = Config()
        return setup_logger(cfg)
    except Exception:
        return logging.getLogger()

def set_tts_config(config_instance: Config):
    """Sets the global config instance for the TTS module."""
    global _config
    _config = config_instance

def _sanitize_text(text: str) -> str:
    """
    Sanitizes text to improve TTS pronunciation by removing symbols and emoticons.
    """
    # Remove unwanted symbols
    symbols_to_remove_pattern = re.compile(r'[\\#@&%$*+=<>/|~^`\[\]{}]+')
    sanitized = symbols_to_remove_pattern.sub("", text)

    # Convert "1:" "2:" etc. into "1." "2."
    sanitized = re.sub(r"(?m)(\d+):", r"\1.", sanitized)

    # Remove Unicode emojis/emoticons
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "\U00002500-\U00002BEF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9ff"
        "\U0001fa70-\U0001faff"
        "]+",
        flags=re.UNICODE
    )
    sanitized = emoji_pattern.sub("", sanitized)

    # Remove common text-based emoticons
    text_emoticons_to_remove = {
        ':)', ':-D', ':D', ':(', ':-(', ';)', ':P', ':-P', ':O', ':-O', '<3', 'xD',
        ':|', ':-|', ':*', ':-*', ':/', ':-/', ':\\', ':-\\'
    }
    for emo in text_emoticons_to_remove:
        sanitized = sanitized.replace(emo, "")

    # Collapse multiple whitespace/newlines into a single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    return sanitized

async def speak(text: str):
    """
    Converts text to speech using Edge-TTS, with pyttsx3 as a fallback.
    Uses a secure temporary file for each speech output, then deletes it.
    """
    logger = _get_logger()

    if not _config:
        logger.error("TTS config not set. Cannot speak.")
        print(Fore.RED + "TTS config not set. Cannot speak." + Style.RESET_ALL)
        return

    safe_text = _sanitize_text(text)

    # Choose engine: Edge-TTS or pyttsx3
    if edge_tts is None or _config.TTS_ENGINE.lower() == 'pyttsx3':
        logger.info("Using pyttsx3 fallback for TTS.")
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)
        return

    # Create a secure named temporary file for the mp3
    try:
        tmp = tempfile.NamedTemporaryFile(prefix="zira_tts_", suffix=".mp3", delete=False)
        temp_audio_file = tmp.name
        tmp.close()
        # Restrict permissions to owner read/write only
        os.chmod(temp_audio_file, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        logger.error("Failed to create secure temporary file for TTS: %s", e, exc_info=True)
        print(Fore.RED + "Could not create temporary file for TTS." + Style.RESET_ALL)
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)
        return

    try:
        # Generate speech to temp file using configured Edge voice
        voice_name = _config.TTS_EDGE_VOICE_NAME
        communicate = edge_tts.Communicate(safe_text, voice_name)
        await communicate.save(temp_audio_file)

        # Play via ffplay (FFmpeg). -nodisp hides video, -autoexit closes when done.
        process = await asyncio.create_subprocess_exec(
            "ffplay",
            "-nodisp",
            "-autoexit",
            temp_audio_file,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.wait()

    except FileNotFoundError:
        logger.warning("ffplay not found. Falling back to pyttsx3.")
        print(Fore.RED + "ffplay not found. Falling back to pyttsx3." + Style.RESET_ALL)
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)

    except Exception as e:
        logger.error("Error during Edge-TTS playback: %s", e, exc_info=True)
        print(Fore.RED + f"TTS playback error: {e}" + Style.RESET_ALL)
        print(Fore.YELLOW + "Falling back to pyttsx3 TTS." + Style.RESET_ALL)
        _speak_pyttsx3_fallback(safe_text, _config.TTS_PYTTSX3_VOICES)

    finally:
        # Attempt to delete the temporary file
        try:
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
                logger.debug("Temporary TTS file removed: %s", temp_audio_file)
        except Exception as e:
            logger.warning("Could not remove temp TTS file %s: %s", temp_audio_file, e)

def _speak_pyttsx3_fallback(text: str, preferred_voices: list):
    """
    Fallback function for TTS using pyttsx3.
    The input text is assumed to have been sanitized already.
    """
    logger = _get_logger()
    try:
        engine = pyttsx3.init("sapi5")  # 'sapi5' for Windows, 'nsss' for macOS, 'espeak' for Linux
        voices = engine.getProperty("voices")
        selected_voice = None
        for voice in voices:
            for preferred in preferred_voices:
                if preferred.lower() in voice.name.lower():
                    selected_voice = voice.id
                    break
            if selected_voice:
                break

        if selected_voice:
            engine.setProperty("voice", selected_voice)

        engine.say(text)
        engine.runAndWait()
        logger.info("pyttsx3 spoke text successfully.")
    except Exception as e:
        logger.error("Error in pyttsx3 TTS fallback: %s", e, exc_info=True)
        print(Fore.RED + "Error in pyttsx3 TTS fallback." + Style.RESET_ALL)
        print(Fore.RED + "Please ensure pyttsx3 is installed and configured." + Style.RESET_ALL)
