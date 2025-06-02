# tools/system_tools.py

import subprocess
import webbrowser
import asyncio
import os
import signal
from langchain.tools import tool
from core.tts import speak # speak will now internally use the Config

# No direct changes needed here, as the tools themselves don't use config directly.
# The 'speak' function they call will handle config internally.

@tool
async def open_application(app_name: str):
    """Opens the specified application."""
    try:
        subprocess.Popen([app_name])
        response_text = f"Opening {app_name}."
        await speak(response_text)
        return response_text
    except FileNotFoundError:
        response_text = f"Application '{app_name}' not found."
        await speak(response_text)
        return response_text
    except Exception as e:
        response_text = f"Error opening {app_name}: {e}"
        await speak(response_text)
        return response_text

@tool
async def close_application(app_name: str):
    """
    Attempts to close the specified application.
    On Windows, runs `taskkill /IM <app_name>.exe /F`.
    On macOS/Linux, uses `pkill -f <baseName>`.
    Example: close_application("notepad.exe")
    """
    proc = app_name.strip()

    if os.name == "nt":
        # Ensure “.exe” is appended if missing
        if not proc.lower().endswith(".exe"):
            proc += ".exe"
        cmd = ["taskkill", "/IM", proc, "/F"]
    else:
        # macOS/Linux: strip extension, then pkill -f
        base = os.path.splitext(proc)[0]
        cmd = ["pkill", "-f", base]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            response_text = f"Closed `{app_name}` successfully."
        else:
            stderr = result.stderr.strip()
            response_text = (
                f"Couldn’t close `{app_name}` (code {result.returncode}).\n"
                f"Error: {stderr}"
            )
    except FileNotFoundError:
        response_text = (
            f"Could not find system command to close `{app_name}`. "
            "Ensure you're on a supported OS."
        )
    except Exception as e:
        response_text = f"An unexpected error occurred while closing `{app_name}`: {e}"

    await speak(response_text)
    return response_text

@tool
async def open_website(url: str):
    """Opens the specified website."""
    try:
        webbrowser.open(url)
        response_text = f"Opening website: {url}."
        await speak(response_text)
        return response_text
    except Exception as e:
        response_text = f"Error opening {url}: {e}"
        await speak(response_text)
        return response_text

@tool
async def get_weather(location: str):
    """Gets the current weather for the specified location (placeholder)."""
    response_text = f"Getting weather for {location}... (Weather data not yet implemented)."
    await speak(response_text)
    return response_text
