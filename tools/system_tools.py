# tools/system_tools.py

import subprocess
import webbrowser
import os
import re                  # For URL validation & location sanitization
import httpx               # Using the synchronous client for get_weather
from core.config import Config  # Import Config to access system configurations

# Instantiate Config at import time (keys are frozen until restart)
_config = Config()

# -----------------------------------------------------------------------------
# CRITICAL SECURITY: Whitelisting of Allowed Applications
#
# Only add applications here that you explicitly trust and want Zira to control.
# Use full paths or trusted executable names in PATH. This prevents arbitrary code execution.
# -----------------------------------------------------------------------------
_ALLOWED_APPLICATIONS = {
    # Windows examples (either full path or relying on PATH)
    "notepad":    "notepad.exe",
    "chrome":     "chrome.exe",
    "calculator": "calc.exe",
    "vscode":     "Code.exe",
    # Linux/macOS examples (uncomment and adjust for your system):
    # "firefox":   "/usr/bin/firefox",
    # "calculator":"/usr/bin/gnome-calculator",
    # "safari":    "/Applications/Safari.app/Contents/MacOS/Safari",
}

# Mapping from macOS .app bundle names → process names used by `pkill`
_MACOS_APP_BUNDLE_TO_PROCESS_NAME = {
    "safari.app":     "Safari",
    "calculator.app": "Calculator",
    "terminal.app":   "Terminal",
}


def _get_app_path(app_name: str) -> str | None:
    """
    Returns the full path (or executable name) for a whitelisted application.
    Returns None if not whitelisted or not executable/found.
    """
    normalized_app_name = app_name.lower().replace(".exe", "").strip()

    if normalized_app_name in _ALLOWED_APPLICATIONS:
        full_path = _ALLOWED_APPLICATIONS[normalized_app_name]

        # If given as a full path, verify it exists and is executable
        if os.path.isabs(full_path) and os.path.exists(full_path) and os.access(full_path, os.X_OK):
            return full_path

        # On Windows, allow just "notepad.exe" or similar if in PATH
        if os.name == "nt" and full_path.lower().endswith(".exe"):
            return full_path

        # If the entry wasn’t an absolute path, fail-secure
        return None

    return None


# Regex for basic URL validation (must start with http:// or https:// or ftp://)
_VALID_URL_REGEX = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https:// or ftp://
    r'(?:(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+'  # domain...
    r'(?:[A-Za-z]{2,6}|[A-Za-z0-9-]{2,})|'  # domain TLDs
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or IP
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)


def open_application(app_name: str) -> str:
    """
    Opens a whitelisted application by name (e.g., "notepad").
    SECURITY: Only whitelisted names are allowed.
    """
    if not isinstance(app_name, str) or not app_name.strip():
        return "Please specify a valid application name."

    app_path = _get_app_path(app_name)
    if not app_path:
        return f"Application '{app_name}' is not recognized or not allowed."

    try:
        # Use subprocess.Popen with shell=False to prevent shell injection
        subprocess.Popen([app_path])
        return f"Opening {app_name}."
    except FileNotFoundError:
        return f"Executable for '{app_name}' not found in PATH or at expected path."
    except PermissionError:
        return f"Permission denied when trying to open '{app_name}'."
    except Exception:
        return f"An unexpected error occurred while trying to open '{app_name}'."


def close_application(app_name: str) -> str:
    """
    Closes a whitelisted application by name (e.g., "notepad").
    SECURITY: Only whitelisted names are allowed.
    """
    if not isinstance(app_name, str) or not app_name.strip():
        return "Please specify a valid application name to close."

    normalized = app_name.lower().replace(".exe", "").strip()
    if normalized not in _ALLOWED_APPLICATIONS:
        return f"Application '{app_name}' is not recognized or not allowed."

    proc_target = app_name.strip()

    if os.name == "nt":
        # Ensure ".exe" suffix for Windows taskkill
        if not proc_target.lower().endswith(".exe"):
            proc_target += ".exe"
        cmd = ["taskkill", "/IM", proc_target, "/F"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return f"Closed '{app_name}' successfully."
            stderr = result.stderr.strip()
            return (
                f"Could not close '{app_name}' (exit code {result.returncode}). "
                f"{'Error: ' + stderr if stderr else 'No additional error info.'}"
            )
        except FileNotFoundError:
            return "System command for closing applications not found on this OS."
        except PermissionError:
            return f"Permission denied when trying to close '{app_name}'."
        except Exception:
            return f"An unexpected error occurred while trying to close '{app_name}'."
    else:
        # macOS/Linux: Map "Something.app" to its process name
        if proc_target.lower().endswith(".app"):
            proc_target_lower = proc_target.lower()
            proc_target = _MACOS_APP_BUNDLE_TO_PROCESS_NAME.get(
                proc_target_lower,
                os.path.splitext(proc_target_lower)[0]
            )
        else:
            proc_target = os.path.splitext(proc_target)[0]
        cmd = ["pkill", "-f", proc_target]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return f"Closed '{app_name}' successfully."
            stderr = result.stderr.strip()
            return (
                f"Could not close '{app_name}' (exit code {result.returncode}). "
                f"{'Error: ' + stderr if stderr else 'No additional error info.'}"
            )
        except FileNotFoundError:
            return "System command for closing applications not found on this OS."
        except PermissionError:
            return f"Permission denied when trying to close '{app_name}'."
        except Exception:
            return f"An unexpected error occurred while trying to close '{app_name}'."


def open_website(url: str) -> str:
    """
    Opens a valid URL in the default web browser.
    SECURITY: Validates URL format and enforces length limits.
    """
    if not isinstance(url, str) or not url.strip():
        return "Please provide a non-empty URL."

    url = url.strip()
    if len(url) > 2083:
        return "URL is too long to open safely."

    if not _VALID_URL_REGEX.match(url):
        return "That doesn't look like a valid website address. Provide a full URL starting with http:// or https://."

    try:
        webbrowser.open(url)
        return f"Opening website: {url}."
    except Exception:
        return f"Sorry, I encountered an error trying to open '{url}'."


def get_weather(location: str) -> str:
    """
    Fetches current weather for a sanitized location via OpenWeatherMap API.
    SECURITY: Sanitizes location and handles API errors gracefully.
    """
    if not isinstance(location, str) or not location.strip():
        return "Please specify a location for the weather query."

    # Sanitize location: keep only letters, spaces, and hyphens
    safe_location = re.sub(r"[^A-Za-z\s\-]", "", location).strip()
    if not safe_location:
        return "Please provide a valid location with letters only."

    api_key = _config.OPENWEATHER_API_KEY
    base_url = _config.OPENWEATHER_BASE_URL
    units = "metric"

    params = {
        "q": safe_location,
        "appid": api_key,
        "units": units
    }

    try:
        # Use the synchronous HTTPX client so we can keep this function def‑based
        with httpx.Client() as client:
            response = client.get(base_url, params=params)
            response.raise_for_status()

        data = response.json()

        # If city not found
        if data.get("cod") == "404":
            return f"Could not find weather data for '{safe_location}'. Please check the spelling."
        
        main_data    = data.get("main", {})
        weather_desc = data.get("weather", [{}])[0].get("description", "N/A")
        temperature  = main_data.get("temp", "N/A")
        feels_like   = main_data.get("feels_like", "N/A")
        humidity     = main_data.get("humidity", "N/A")
        wind_speed   = data.get("wind", {}).get("speed", "N/A")
        city_name    = data.get("name", safe_location)

        return (
            f"The weather in {city_name} is currently {weather_desc}. "
            f"Temperature: {temperature}°C (feels like {feels_like}°C). "
            f"Humidity: {humidity}%. Wind speed: {wind_speed} m/s."
        )

    except httpx.RequestError:
        return "I couldn't connect to the weather service. Please check your internet connection."
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            return "There's an issue with the weather API key. Please ensure it's correct."
        elif status == 404:
            return f"Could not find weather data for '{safe_location}'. Please check the spelling."
        else:
            return f"The weather service returned an error (Status {status}). Please try again later."
    except Exception:
        return f"An unexpected error occurred while trying to get weather for '{safe_location}'."
