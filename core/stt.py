# core/stt.py
import speech_recognition as sr
import keyboard
import asyncio
import pyaudio
from core.tts import speak  # Import speak for feedback

def find_microphone_index(preferred_names):
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

async def transcribe_from_push_to_talk(push_key='alt'):
    """Transcribes audio while the specified key is held down."""
    preferred_mics = [
        "Realtek(R) Audio",
        "HD Audio Mic",
        "Microphone",
        "Hands-Free HF Audio"
    ]
    mic_index = find_microphone_index(preferred_mics)

    r = sr.Recognizer()
    mic = sr.Microphone(device_index=mic_index) if mic_index is not None else sr.Microphone()

    print(f"Press and hold '{push_key}' to speak...")
    await speak(f"Press and hold '{push_key}' to speak...")

    while True:
        if keyboard.is_pressed(push_key):
            print("Listening...")
            await speak("Listening...")
            try:
                with mic as source:
                    r.adjust_for_ambient_noise(source)  # Adjust for noise once
                    audio = r.listen(source)
                print("Processing audio...")
                await speak("Processing audio...")
                text = r.recognize_google(audio)  # You can change the recognizer
                print(f"You said: {text}")
                return text
            except sr.WaitTimeoutError:
                print("No speech detected.")
                await speak("No speech detected.")
            except sr.UnknownValueError:
                print("Could not understand audio.")
                await speak("Could not understand audio.")
            except sr.RequestError as e:
                print(f"Could not request results from speech recognition service; {e}")
                await speak("Speech recognition service error.")
            finally:
                # Wait a bit to avoid rapid triggering if key is still held
                await asyncio.sleep(0.2)
        await asyncio.sleep(0.1)

if __name__ == '__main__':
    async def main():
        transcribed_text = await transcribe_from_push_to_talk()
        if transcribed_text:
            print(f"Transcribed: {transcribed_text}")
    asyncio.run(main())