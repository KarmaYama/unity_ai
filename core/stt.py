# core/stt.py

import asyncio
import logging
import speech_recognition as sr
import keyboard
import pyaudio
from core.tts import speak
from core.config import Config
from core.logger_config import setup_logger  # To get a shared logger

def find_microphone_index(preferred_names: list[str], logger: logging.Logger) -> int | None:
    """
    Returns the index of a microphone whose name matches one of the preferred names.
    If none found, returns None.

    Security/Resource Note:
    - Ensures PyAudio instance is terminated after scanning.
    """
    p = None
    try:
        p = pyaudio.PyAudio()
    except Exception as e:
        logger.error("Failed to initialize PyAudio: %s", e, exc_info=True)
        return None

    try:
        for i in range(p.get_device_count()):
            try:
                dev = p.get_device_info_by_index(i)
                name = dev.get("name", "")
                input_channels = dev.get("maxInputChannels", 0)
            except Exception as e:
                logger.warning("Error querying device index %s: %s", i, e)
                continue

            if input_channels > 0:
                for preferred in preferred_names:
                    if preferred.lower() in name.lower():
                        logger.info("Selected microphone: %s (Index: %d)", name, i)
                        return i
    finally:
        # Always terminate the PyAudio instance to free resources
        try:
            p.terminate()
        except Exception:
            pass

    logger.warning("No preferred microphone found.")
    return None


async def listen_and_transcribe(
    mic_index: int,
    logger: logging.Logger,
    timeout: float = 5.0,
    phrase_time_limit: float = 10.0
) -> str | None:
    """
    Performs a single listen/transcribe cycle using the specified microphone index.
    - timeout: max seconds to wait for the user to start speaking
    - phrase_time_limit: max seconds of audio to record once speech starts
    Returns the recognized text or None.
    """
    r = sr.Recognizer()

    try:
        mic = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()
    except Exception as e:
        logger.error("Could not open microphone (index=%s): %s", mic_index, e, exc_info=True)
        await speak("Microphone unavailable.")
        return None

    await speak("Listening...")
    logger.info("Listening on microphone index %s", mic_index)

    def _record() -> str | None:
        """
        Runs in a background thread. Listens with timeouts to avoid blocking forever.
        """
        try:
            with mic as source:
                r.adjust_for_ambient_noise(source)
                # Wait 'timeout' sec for phrase start, then record up to phrase_time_limit
                audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            logger.info("Audio captured, sending to recognizer...")
            text = r.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            logger.warning("WaitTimeoutError: No speech detected within %s seconds.", timeout)
            return None
        except sr.UnknownValueError:
            logger.warning("UnknownValueError: Could not understand audio.")
            return ""
        except sr.RequestError as e:
            logger.error("RequestError: Speech recognition service error: %s", e, exc_info=True)
            return ""
        except Exception as e:
            logger.error("Unexpected error during recording/transcription: %s", e, exc_info=True)
            return None

    # Run the blocking portion in a thread to avoid blocking the event loop
    text = await asyncio.to_thread(_record)

    if text is None:
        await speak("No speech detected or an error occurred.")
        return None

    if text == "":
        await speak("Could not understand audio.")
        return None

    logger.info("Transcribed text: %s", text)
    return text


async def transcribe_from_push_to_talk(
    config: Config,
    logger: logging.Logger | None = None
) -> str | None:
    """
    Waits for the configured push-key to be pressed, then records and returns a single transcription.
    - Uses 'keyboard.wait' rather than a global hook to reduce side effects.
    """
    if logger is None:
        logger = setup_logger(config, name="stt_logger")

    preferred_mics = config.STT_PREFERRED_MICS
    key_name = config.STT_PUSH_TO_TALK_KEY.lower()

    mic_index = find_microphone_index(preferred_mics, logger)
    if mic_index is None:
        logger.error("No valid microphone found. Aborting transcription.")
        await speak("No valid microphone found.")
        return None

    prompt_msg = f"Press and hold '{key_name}' to speak."
    await speak(prompt_msg)
    logger.info("Waiting for '%s' key to be pressed...", key_name)

    try:
        # Blocks until the push-to-talk key is pressed
        keyboard.wait(key_name)
        logger.info("Push-to-talk key pressed. Starting transcription.")
        # Now perform the listen/transcribe cycle
        return await listen_and_transcribe(mic_index, logger)
    except KeyboardInterrupt:
        logger.info("Transcription stopped by user (KeyboardInterrupt).")
        await speak("Transcription stopped.")
    except Exception as e:
        logger.error("Error in push-to-talk loop: %s", e, exc_info=True)
        await speak("An error occurred during transcription.")
    finally:
        # Ensure keyboard hooks are cleared if any got registered (just in case)
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    return None


# If run directly, do a quick test
if __name__ == '__main__':
    async def main():
        cfg = Config()
        log = setup_logger(cfg, name="stt_test_logger")
        print("Testing speech-to-text. Press and hold the configured push-to-talk key.")
        spoken = await transcribe_from_push_to_talk(config=cfg, logger=log)
        if spoken:
            print(f"You said: {spoken}")
        else:
            print("No speech transcribed or an error occurred.")

    asyncio.run(main())
