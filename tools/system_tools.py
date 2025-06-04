import subprocess
import webbrowser
import asyncio
import os
import signal
import re # Added for URL validation
from langchain.tools import tool
from core.tts import speak
from core.config import Config # Import Config to access system configurations

# Instantiate Config to use its properties
_config = Config()

# -----------------------------------------------------------------------------
# CRITICAL SECURITY: Whitelisting of Allowed Applications
# This is the PRIMARY control to prevent arbitrary code execution via
# 'open_application' and 'close_application' tools.
# ONLY add applications here that you explicitly trust and want Zira to control.
# Use the FULL PATH to the executable to prevent PATH variable manipulation.
#
# Examples (customize for your OS and installed applications):
# On Windows: C:\Windows\System32\notepad.exe, C:\Program Files\Google\Chrome\Application\chrome.exe
# On macOS: /Applications/Safari.app, /System/Applications/Calculator.app
# On Linux: /usr/bin/gnome-calculator, /usr/bin/firefox
# -----------------------------------------------------------------------------
_ALLOWED_APPLICATIONS = {
    # Application display name (case-insensitive for user input) : Full path to executable
    "notepad": "notepad.exe", # Windows example
    "chrome": "chrome.exe",   # Windows example (assumes it's in PATH or specific path)
    "calculator": "calc.exe", # Windows example
    "vscode": "Code.exe",     # Windows example
    # Linux/macOS examples (uncomment and adjust for your system)
    # "firefox": "/usr/bin/firefox",
    # "calculator": "/usr/bin/gnome-calculator",
    # "safari": "/Applications/Safari.app/Contents/MacOS/Safari", # macOS specific
    # "terminal": "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal", # macOS specific
}

# Add macOS .app bundle paths to a lookup for `pkill` if they exist
_MACOS_APP_BUNDLE_TO_PROCESS_NAME = {
    "safari.app": "Safari",
    "calculator.app": "Calculator",
    "terminal.app": "Terminal",
    # Add more as needed
}

def _get_app_path(app_name: str) -> str | None:
    """
    Returns the full path to an application if it's in the whitelist,
    otherwise returns None. Handles OS-specific executable names.
    """
    # Normalize app_name for lookup (e.g., remove .exe, lowercase)
    normalized_app_name = app_name.lower().replace(".exe", "")

    if normalized_app_name in _ALLOWED_APPLICATIONS:
        # For Windows, we might return just the .exe name if it's in PATH,
        # or a full path if specified.
        # For Linux/macOS, it should ideally always be a full path.
        full_path = _ALLOWED_APPLICATIONS[normalized_app_name]

        # Basic check for existence and executability (though Popen/run will also check)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK):
            return full_path
        elif os.name == "nt" and full_path.endswith(".exe"):
            # On Windows, if it's just an .exe name, assume it's in PATH and can be found
            return full_path
        else:
            _config.logger.warning(f"Whitelisted app path '{full_path}' not found or not executable.")
            return None
    
    _config.logger.warning(f"Attempted to access non-whitelisted application: {app_name}")
    return None

# Regex for basic URL validation - helps catch obvious non-URLs
_VALID_URL_REGEX = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https:// or ftp:// or ftps://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
    r'(?::\d+)?' # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)


@tool
async def open_application(app_name: str) -> str:
    """
    Opens the specified application.
    SECURITY CRITICAL: Only whitelisted applications are allowed.
    Input: app_name (e.g., "notepad", "chrome")
    """
    _config.logger.info(f"Received request to open application: {app_name}")

    # Input Validation & Whitelisting
    if not isinstance(app_name, str) or not app_name.strip():
        _config.logger.warning("Invalid input for open_application: empty or non-string.")
        response_text = "Please specify a valid application name."
        await speak(response_text)
        return response_text

    app_path = _get_app_path(app_name)

    if app_path:
        try:
            # Command Execution & Safe Subprocess Usage:
            # Use shell=False and pass arguments as a list.
            # This prevents shell injection vulnerabilities.
            # subprocess.Popen is fine here as it's a one-off launch.
            # Least-Privilege Execution: Ensure the user running Zira has
            # minimal necessary permissions.
            subprocess.Popen([app_path]) # No shell=True
            response_text = f"Opening {app_name}."
            _config.logger.info(response_text) # Sanitized logging
            await speak(response_text)
            return response_text
        except FileNotFoundError:
            # This case should ideally be caught by _get_app_path, but as a fallback:
            _config.logger.error(f"Executable not found for whitelisted application '{app_name}' at '{app_path}'.", exc_info=True)
            response_text = f"Application '{app_name}' executable not found at expected path."
            await speak(response_text)
            return response_text
        except PermissionError:
            _config.logger.error(f"Permission denied to open '{app_name}' at '{app_path}'.", exc_info=True)
            response_text = f"Permission denied to open '{app_name}'. Check Zira's privileges."
            await speak(response_text)
            return response_text
        except Exception as e:
            # Fail-Secure Error Handling: Catch unexpected errors.
            _config.logger.error(f"Error opening {app_name} from '{app_path}': {e}", exc_info=True) # Log full error
            response_text = f"An unexpected error occurred while trying to open {app_name}."
            await speak(response_text)
            return response_text
    else:
        response_text = f"Application '{app_name}' is not recognized or not allowed. Please ask me to open a whitelisted application."
        _config.logger.warning(response_text) # Sanitized logging
        await speak(response_text)
        return response_text

@tool
async def close_application(app_name: str) -> str:
    """
    Attempts to close the specified application.
    SECURITY CRITICAL: Only whitelisted applications are allowed to be closed.
    Input: app_name (e.g., "notepad", "chrome")
    """
    _config.logger.info(f"Received request to close application: {app_name}")

    # Input Validation & Whitelisting
    if not isinstance(app_name, str) or not app_name.strip():
        _config.logger.warning("Invalid input for close_application: empty or non-string.")
        response_text = "Please specify a valid application name to close."
        await speak(response_text)
        return response_text

    # Check if the app is in our allowed list, even if we don't need its path for pkill/taskkill directly.
    # This prevents an attacker from trying to close arbitrary processes by name.
    normalized_app_name = app_name.lower().replace(".exe", "")
    if normalized_app_name not in _ALLOWED_APPLICATIONS:
         _config.logger.warning(f"Attempted to close non-whitelisted application: {app_name}")
         response_text = f"Application '{app_name}' is not recognized or not allowed to be closed."
         await speak(response_text)
         return response_text

    proc_target = app_name.strip()
    cmd = []

    if os.name == "nt":
        # Ensure ".exe" is appended if missing for taskkill
        if not proc_target.lower().endswith(".exe"):
            proc_target += ".exe"
        cmd = ["taskkill", "/IM", proc_target, "/F"]
    else: # macOS/Linux
        # For macOS, try to map bundle name to process name (e.g., "Safari.app" -> "Safari")
        if proc_target.lower().endswith(".app"):
            base_name = proc_target.lower().replace(".app", "")
            proc_target = _MACOS_APP_BUNDLE_TO_PROCESS_NAME.get(proc_target.lower(), base_name)
        else:
            # Fallback to just the base name if no .app suffix
            proc_target = os.path.splitext(proc_target)[0]
        
        # Use pkill -f for full process name match, but still
        # ensure the name itself is from our whitelist to avoid
        # accidentally killing critical system processes.
        # This relies on _ALLOWED_APPLICATIONS having sufficient detail.
        cmd = ["pkill", "-f", proc_target]
    
    # Command Execution & Safe Subprocess Usage:
    # Always use subprocess.run with shell=False and explicit argument lists.
    # Least-Privilege Execution: The process running Zira should have minimal permissions.
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False) # check=False to handle non-zero exit codes manually
        
        if result.returncode == 0:
            response_text = f"Closed `{app_name}` successfully."
            _config.logger.info(response_text) # Sanitized logging
        else:
            stderr = result.stderr.strip()
            # Fail-Secure Error Handling: Provide user-friendly feedback, log details.
            response_text = (
                f"Couldn’t close `{app_name}` (code {result.returncode}). "
                f"Error details: {stderr if stderr else 'No specific error message.'}"
            )
            _config.logger.error(f"Failed to close '{app_name}': {stderr}", exc_info=False) # Log specific error
    except FileNotFoundError:
        _config.logger.error(f"System command ('taskkill' or 'pkill') not found on this OS for closing '{app_name}'.", exc_info=True)
        response_text = (
            f"Could not find system command to close `{app_name}`. "
            "Ensure you're on a supported OS or that the necessary utilities are installed."
        )
    except PermissionError:
        _config.logger.error(f"Permission denied to close '{app_name}'.", exc_info=True)
        response_text = f"Permission denied to close '{app_name}'. Check Zira's privileges."
    except Exception as e:
        _config.logger.error(f"An unexpected error occurred while closing `{app_name}`: {e}", exc_info=True)
        response_text = f"An unexpected error occurred while trying to close {app_name}."

    await speak(response_text)
    return response_text

@tool
async def open_website(url: str) -> str:
    """
    Opens the specified website in the default web browser.
    Input: url (e.g., "https://google.com")
    """
    _config.logger.info(f"Received request to open website: {url}")

    # Input Validation: Basic URL format check
    if not isinstance(url, str) or not _VALID_URL_REGEX.match(url):
        _config.logger.warning(f"Invalid or potentially malicious URL detected: {url}")
        response_text = "That doesn't look like a valid website address. Please provide a full URL starting with http:// or https://."
        await speak(response_text)
        return response_text

    # SECURITY NOTE: webbrowser.open() is generally considered safe as it delegates
    # to the OS's default browser, which handles its own sandboxing and security.
    # However, ensure the URL itself isn't crafted to exploit browser vulnerabilities.
    try:
        webbrowser.open(url)
        response_text = f"Opening website: {url}."
        _config.logger.info(response_text) # Sanitized logging
        await speak(response_text)
        return response_text
    except Exception as e:
        # Fail-Secure Error Handling:
        _config.logger.error(f"Error opening website {url}: {e}", exc_info=True)
        response_text = f"Sorry, I encountered an error trying to open {url}."
        await speak(response_text)
        return response_text

@tool
async def get_weather(location: str) -> str:
    """
    Gets the current weather for the specified location (placeholder).
    Input: location (e.g., "London", "New York City")
    """
    _config.logger.info(f"Received request for weather in: {location}")

    # Input Validation: Basic check.
    # CRITICAL: If integrating with a real weather API, this 'location' string
    # MUST be sanitized (e.g., remove special characters, limit length)
    # before being sent in an HTTP request to prevent injection or abuse.
    if not isinstance(location, str) or not location.strip():
        _config.logger.warning("Invalid input for get_weather: empty or non-string location.")
        response_text = "Please specify a location for the weather query."
        await speak(response_text)
        return response_text
    
    # Network & API Call Security (Placeholder for future implementation):
    # - HTTPS Enforcement: Ensure all API calls use HTTPS.
    # - API Response Validation: Validate status codes and content types.
    # - Throttling & Backoff: Implement retry logic for rate-limiting (429) or transient errors.
    # - API Key Management: Load API keys securely via environment variables (from Config).
    
    response_text = f"Getting weather for {location}... (Weather data retrieval is a placeholder and not yet implemented)."
    _config.logger.info(response_text) # Sanitized logging
    await speak(response_text)
    return response_text

