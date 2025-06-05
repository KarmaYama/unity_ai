#core/tts.py

import asyncio
import os
import re
import tempfile
import uuid
import stat
import logging
import platform
import pyttsx3
from colorama import Fore, Style
from core.config import Config
from core.logger_config import setup_logger  # To get a shared logger

try:
    import edge_tts
except ImportError:
    edge_tts = None

# Module‐level placeholders for config and logger; set by set_tts_config()
_config: Config | None = None
_logger: logging.Logger | None = None


def set_tts_config(config_instance: Config):
    """
    Initializes the module‐level Config and Logger for TTS.
    Must be called once (e.g., from main.py) before using speak().
    """
    global _config, _logger

    _config = config_instance
    _logger = setup_logger(config_instance, name="tts_logger")  # Shared logger for all TTS calls


def _sanitize_text(text: str) -> str:
    """
    Sanitizes text to improve TTS pronunciation by removing symbols, emoticons,
    and trimming excessive length.
    """
    # Trim to a reasonable max length (e.g., 1000 chars)
    if len(text) > 1000:
        text = text[:1000] + "…"

    # Remove unwanted symbols (common punctuation that confuses TTS)
    symbols_pattern = re.compile(r'[\\#@&%$*+=<>/|~^`\[\]{}]+')
    sanitized = symbols_pattern.sub("", text)

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

    # Remove common text‐based emoticons
    emoticons = {
        ":)", ":-D", ":D", ":(", ":-(", ";)", ":P", ":-P", ":O", ":-O", "<3", "xD",
        ":|", ":-|", ":*", ":-*", ":/", ":-/", ":\\", ":-\\"
    }
    for emo in emoticons:
        sanitized = sanitized.replace(emo, "")

    # Collapse multiple whitespace/newlines into a single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


async def speak(text: str):
    """
    Converts text to speech using Edge‐TTS (if installed and configured),
    with pyttsx3 as a fallback. Generates a secure temp file, plays it,
    and cleans it up.

    This function never blocks the event loop for more than the TTS
    generation and playback itself. Fallback to pyttsx3 is offloaded
    to a thread if needed.
    """
    global _config, _logger
    if _config is None or _logger is None:
        # Config not set; cannot proceed
        print(Fore.RED + "TTS: Configuration not initialized. Call set_tts_config() first." + Style.RESET_ALL)
        return
    
    # Crucial: Check if TTS is globally enabled via the config object
    if not _config.TTS_ENABLED:
        _logger.debug("TTS is disabled by configuration. Skipping speech.")
        return

    logger = _logger
    safe_text = _sanitize_text(text)

    # Choose engine
    use_pyttsx3 = (
        (edge_tts is None) or 
        (_config.TTS_ENGINE.lower() == "pyttsx3")
    )

    if use_pyttsx3:
        logger.info("Using pyttsx3 fallback TTS.")
        # Offload synchronous pyttsx3 to a thread
        await asyncio.to_thread(_speak_pyttsx3_fallback, safe_text, logger)
        return

    # At this point, edge_tts is available and config asks for it
    # Create a secure temp file for the mp3 output
    temp_audio_file = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            prefix="zira_tts_",
            suffix=".mp3",
            delete=False
        )
        temp_audio_file = tmp.name
        tmp.close()
        os.chmod(temp_audio_file, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        logger.error("TTS: Failed to create temp file: %s", e, exc_info=True)
        # Fallback to pyttsx3 if we cannot write temp
        await asyncio.to_thread(_speak_pyttsx3_fallback, safe_text, logger)
        return

    # Generate speech via Edge‐TTS
    try:
        voice_name = _config.TTS_EDGE_VOICE_NAME
        communicator = edge_tts.Communicate(safe_text, voice_name)
        await communicator.save(temp_audio_file)

        # Play the file using ffplay if available
        # Use a short timeout: if ffplay isn't installed, FileNotFoundError triggers fallback
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
        logger.warning("TTS: 'ffplay' not found. Falling back to pyttsx3.")
        print(Fore.YELLOW + "ffplay not found; using pyttsx3 fallback." + Style.RESET_ALL)
        await asyncio.to_thread(_speak_pyttsx3_fallback, safe_text, logger)

    except Exception as e:
        logger.error("TTS: Edge‐TTS error: %s", e, exc_info=True)
        print(Fore.RED + f"Edge‐TTS playback error: {e}" + Style.RESET_ALL)
        print(Fore.YELLOW + "Falling back to pyttsx3 TTS." + Style.RESET_ALL)
        await asyncio.to_thread(_speak_pyttsx3_fallback, safe_text, logger)

    finally:
        # Always attempt to remove the temp file
        if temp_audio_file and os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
                logger.debug("TTS: Removed temp file %s", temp_audio_file)
            except Exception as e:
                logger.warning("TTS: Could not remove temp file %s: %s", temp_audio_file, e)


def _speak_pyttsx3_fallback(text: str, logger: logging.Logger):
    """
    Synchronous fallback TTS using pyttsx3. Chooses engine based on OS.
    """
    try:
        # Select engine based on platform
        system = platform.system().lower()
        if system == "windows":
            engine = pyttsx3.init("sapi5")
        elif system == "darwin":
            engine = pyttsx3.init("nsss")
        else:
            engine = pyttsx3.init("espeak")

        # Optionally choose a preferred voice if available
        voices = engine.getProperty("voices")
        selected = None
        for voice in voices:
            # Search for any substring match in the voice name
            if _config.TTS_EDGE_VOICE_NAME.lower() in voice.name.lower():
                selected = voice.id
                break
        if selected:
            engine.setProperty("voice", selected)

        engine.say(text)
        engine.runAndWait()
        logger.info("TTS (pyttsx3) spoke text successfully.")
    except Exception as e:
        logger.error("TTS: pyttsx3 fallback error: %s", e, exc_info=True)
        print(Fore.RED + "Error in pyttsx3 TTS fallback. Ensure pyttsx3 is installed." + Style.RESET_ALL)

