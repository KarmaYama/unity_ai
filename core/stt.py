# core/stt.py

import speech_recognition as sr
import keyboard
import asyncio
import pyaudio
from core.tts import speak # This import is fine, speak will get config internally
from core.config import Config # Import Config to get settings

# Global config instance (assuming it's initialized in main and passed down)
# For this module, we'll assume it's passed into the functions that need it.

def find_microphone_index(preferred_names: list):
    """
    Returns the index of a microphone whose name matches one of the preferred names.
    If none found, returns None.
    """
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        name = dev['name']
        input_channels = dev.get('maxInputChannels', 0)
        if input_channels > 0:
            for preferred in preferred_names:
                if preferred.lower() in name.lower():
                    print(f"[INFO] Selected microphone: {name} (Index: {i})")
                    return i
    print("[WARNING] No preferred microphone found.")
    return None

async def listen_and_transcribe(mic_index):
    """
    Performs a single listen/transcribe cycle using the specified microphone index.
    Speaks and prints status messages.
    """
    r = sr.Recognizer()
    mic = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()

    await speak("Listening...")
    print("Listening...")

    try:
        with mic as source:
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source)
        print("Processing audio...")
        await speak("Processing audio...")
        text = r.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.WaitTimeoutError:
        print("No speech detected.")
        await speak("No speech detected.")
    except sr.UnknownValueError:
        print("Could not understand audio.")
        await speak("Could not understand audio.")
    except sr.RequestError as e:
        print(f"Could not request results: {e}")
        await speak("Speech recognition service error.")
    return None

async def transcribe_from_push_to_talk(push_key='ctrl', config: Config = None):
    """
    Waits for the specified key (Ctrl) to be pressed, then records and returns a single transcription.
    Does NOT re-prompt — assumes you’ve already been told “press and hold Ctrl to speak.”
    Now accepts a Config object to get preferred mics and push key.
    """
    # Use config for preferred mics and push key, with fallbacks for testing
    if config:
        preferred_mics = config.STT_PREFERRED_MICS
        push_key = config.STT_PUSH_TO_TALK_KEY
    else:
        preferred_mics = [
            "Realtek(R) Audio",
            "HD Audio Mic",
            "Microphone",
            "Hands-Free HF Audio"
        ]
        push_key = 'ctrl' # Default if config is not provided (e.g., for direct script execution)

    mic_index = find_microphone_index(preferred_mics)

    # Immediately start waiting for Ctrl; do not print or speak any additional prompts here.
    loop = asyncio.get_event_loop()
    transcription_event = asyncio.Event()
    transcribed_text = None

    def on_key_event(e):
        # Trigger on key-down of the specified push_key if event isn't already set
        if (
            e.event_type == 'down'
            and e.name.lower() == push_key.lower() # Compare with configured push_key
            and not transcription_event.is_set()
        ):
            loop.call_soon_threadsafe(transcription_event.set)

    keyboard.hook(on_key_event)

    try:
        # Wait for push_key-down
        await transcription_event.wait()
        transcription_event.clear()

        # Once push_key is detected, record and transcribe
        text = await listen_and_transcribe(mic_index)
        if text:
            transcribed_text = text

    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        keyboard.unhook_all()
        print("Keyboard hook removed.")
        return transcribed_text

if __name__ == '__main__':
    async def main():
        # For testing, create a dummy config or load it
        test_config = Config() # This will load from .env if it exists
        print(f"Testing speech-to-text. Press and hold {test_config.STT_PUSH_TO_TALK_KEY} to speak.")
        spoken_text = await transcribe_from_push_to_talk(config=test_config)
        if spoken_text:
            print(f"You said: {spoken_text}")
        else:
            print("No speech transcribed.")
    asyncio.run(main())
