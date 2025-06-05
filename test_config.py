import os
from core.config import Config
import inspect # Used to inspect attributes of the Config class
from datetime import datetime

def mask_sensitive_value(key: str, value: any) -> str:
    """
    Masks sensitive values (like API keys) for display.
    Masks all but the first and last 4 characters of the value if it's a string
    and the key name suggests it's sensitive.
    """
    if not isinstance(value, str):
        return repr(value) # Return non-string values as their representation

    # Define patterns for sensitive keys
    sensitive_patterns = ["_API_KEY", "_SECRET", "_TOKEN", "_PASSWORD"]

    # Check if the key matches any sensitive pattern (case-insensitive)
    if any(pattern in key.upper() for pattern in sensitive_patterns):
        if not value or len(value) <= 8:
            return "********" # Mask short or empty keys completely
        return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
    
    return repr(value) # Return non-sensitive string values as their representation


try:
    cfg = Config()
except Exception as e:
    print(f"ERROR: Config initialization failed: {e}")
    # Log the full traceback for debugging
    import traceback
    traceback.print_exc()
    exit(1)

print(f"--- Zira Configuration Test Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
print("\n--- API Keys & Secrets ---")
# Dynamically get all attributes of the Config object
# Using vars(cfg) gets instance attributes. For class attributes, you might use inspect.getmembers.
# For simplicity, we'll focus on instance attributes set in __init__.
config_attributes = sorted([attr for attr in vars(cfg) if not attr.startswith('_')]) # Filter out private attributes

# Group attributes for better display
grouped_attributes = {
    "API Keys & Secrets": [],
    "LLM Configuration": [],
    "Assistant Persona & Prompts": [],
    "Logging Configuration": [],
    "Speech-to-Text (STT) Configuration": [],
    "Text-to-Speech (TTS) Configuration": [],
    "Agent Tools Configuration": [],
    "Other": [] # Catch-all for anything not explicitly categorized
}

# Manually categorize based on your Config class structure
for attr_name in config_attributes:
    if attr_name.endswith("_API_KEY") or attr_name.endswith("_SECRET"):
        grouped_attributes["API Keys & Secrets"].append(attr_name)
    elif attr_name.startswith("LLM_"):
        grouped_attributes["LLM Configuration"].append(attr_name)
    elif attr_name.startswith("ASSISTANT_"):
        grouped_attributes["Assistant Persona & Prompts"].append(attr_name)
    elif attr_name.startswith("LOG_") or attr_name.startswith("LOGGER_"):
        grouped_attributes["Logging Configuration"].append(attr_name)
    elif attr_name.startswith("STT_"):
        grouped_attributes["Speech-to-Text (STT) Configuration"].append(attr_name)
    elif attr_name.startswith("TTS_"):
        grouped_attributes["Text-to-Speech (TTS) Configuration"].append(attr_name)
    elif attr_name.startswith("AGENT_") or attr_name.startswith("OPENWEATHER_"): # Added OPENWEATHER_ for new weather config
        grouped_attributes["Agent Tools Configuration"].append(attr_name)
    else:
        grouped_attributes["Other"].append(attr_name)

# Print categorized attributes
for category, attrs in grouped_attributes.items():
    if attrs: # Only print categories that have attributes
        print(f"\n--- {category} ---")
        for attr_name in sorted(attrs): # Sort within categories for consistent output
            attr_value = getattr(cfg, attr_name)
            masked_value = mask_sensitive_value(attr_name, attr_value)
            print(f"{attr_name.ljust(30)} = {masked_value}")

print("\n--- End of Report ---")

