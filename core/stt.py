# core/stt.py

import asyncio
import os
import logging
import speech_recognition as sr
import keyboard
import pyaudio
from core.tts import speak
from core.config import Config

# Attempt to grab a shared logger if one exists in the running app
def _get_logger() -> logging.Logger:
    try:
        from core.logger_config import setup_logger
        cfg = Config()
        return setup_logger(cfg)
    except Exception:
        # If logger setup fails (e.g., before Config), fallback to root logger
        return logging.getLogger()

def find_microphone_index(preferred_names: list):
    """
    Returns the index of a microphone whose name matches one of the preferred names.
    If none found, returns None.
    """
    logger = _get_logger()
    try:
        p = pyaudio.PyAudio()
    except Exception as e:
        logger.error("Failed to initialize PyAudio: %s", e, exc_info=True)
        return None

    for i in range(p.get_device_count()):
        try:
            dev = p.get_device_info_by_index(i)
            name = dev.get('name', '')
            input_channels = dev.get('maxInputChannels', 0)
        except Exception as e:
            logger.warning("Error querying device index %s: %s", i, e)
            continue

        if input_channels > 0:
            for preferred in preferred_names:
                if preferred.lower() in name.lower():
                    logger.info("Selected microphone: %s (Index: %d)", name, i)
                    return i

    logger.warning("No preferred microphone found.")
    return None

async def listen_and_transcribe(mic_index):
    """
    Performs a single listen/transcribe cycle using the specified microphone index.
    Speaks and logs status messages. Returns the recognized text or None.
    """
    logger = _get_logger()
    r = sr.Recognizer()

    try:
        mic = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()
    except Exception as e:
        logger.error("Could not open microphone (index=%s): %s", mic_index, e, exc_info=True)
        await speak("Microphone unavailable.")
        return None

    await speak("Listening...")
    logger.info("Listening on microphone index %s", mic_index)

    try:
        with mic as source:
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source)
        logger.info("Audio captured, processing...")
        await speak("Processing audio...")
        text = r.recognize_google(audio)
        logger.info("Transcribed text: %s", text)
        return text
    except sr.WaitTimeoutError:
        logger.warning("No speech detected.")
        await speak("No speech detected.")
    except sr.UnknownValueError:
        logger.warning("Could not understand audio.")
        await speak("Could not understand audio.")
    except sr.RequestError as e:
        logger.error("Speech recognition service error: %s", e, exc_info=True)
        await speak("Speech recognition service error.")
    except Exception as e:
        logger.error("Unexpected error during transcription: %s", e, exc_info=True)
        await speak("An error occurred during transcription.")
    return None

async def transcribe_from_push_to_talk(push_key: str = 'ctrl', config: Config = None):
    """
    Waits for the specified push_key to be pressed, then records and returns a single transcription.
    Does NOT re-prompt—assumes you've already been told “press and hold <push_key> to speak.”
    Accepts a Config object to determine STT_PREFERRED_MICS and STT_PUSH_TO_TALK_KEY.
    """
    logger = _get_logger()
    # Use config push_key if provided, otherwise use the function argument
    if config:
        preferred_mics = config.STT_PREFERRED_MICS
        key_name = config.STT_PUSH_TO_TALK_KEY.lower()
    else:
        preferred_mics = ["Realtek(R) Audio", "HD Audio Mic", "Microphone", "Hands-Free HF Audio"]
        key_name = push_key

    mic_index = find_microphone_index(preferred_mics)
    if mic_index is None:
        logger.error("No valid microphone found. Aborting transcription.")
        await speak("No valid microphone found.")
        return None

    loop = asyncio.get_event_loop()
    transcription_event = asyncio.Event()
    transcribed_text = None

    def on_key_event(e):
        # Trigger on key-down of the configured push_key if event isn't already set
        # e.name might be 'ctrl', 'left ctrl', 'right ctrl', etc., so compare with key_name
        if e.event_type == 'down' and e.name.lower() == key_name and not transcription_event.is_set():
            loop.call_soon_threadsafe(transcription_event.set)

    # Hook the keyboard event
    keyboard.hook(on_key_event)
    logger.info("Keyboard hook established. Waiting for '%s' key to be pressed...", key_name)

    try:
        await transcription_event.wait()
        transcription_event.clear()
        logger.info("Push-to-talk key pressed. Starting transcription.")
        text = await listen_and_transcribe(mic_index)
        if text:
            transcribed_text = text
    except KeyboardInterrupt:
        logger.info("Transcription stopped by user (KeyboardInterrupt).")
        await speak("Transcription stopped.")
    except Exception as e:
        logger.error("Error in push-to-talk loop: %s", e, exc_info=True)
        await speak("An error occurred in the transcription loop.")
    finally:
        keyboard.unhook_all()
        logger.info("Keyboard hook removed.")
        return transcribed_text


# If run directly, do a quick test
if __name__ == '__main__':
    async def main():
        test_config = Config()
        print("Testing speech-to-text. Press and hold the configured push-to-talk key.")
        spoken_text = await transcribe_from_push_to_talk(config=test_config)
        if spoken_text:
            print(f"You said: {spoken_text}")
        else:
            print("No speech transcribed or an error occurred.")

    asyncio.run(main())
