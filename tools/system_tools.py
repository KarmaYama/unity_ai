# tools/system_tools.py
import subprocess
import webbrowser
import asyncio
from langchain.tools import tool
from core.tts import speak

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