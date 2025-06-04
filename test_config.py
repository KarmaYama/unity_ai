# test_config.py

import os
from core.config import Config

def mask_api_key(api_key: str) -> str:
    """Mask all but the first and last 4 characters of the API key."""
    if not api_key or len(api_key) <= 8:
        return "********"
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"

try:
    cfg = Config()
except Exception as e:
    print("Config initialization error:", e)
    exit(1)

masked_key = mask_api_key(cfg.GOOGLE_API_KEY)

print("GOOGLE_API_KEY       =", repr(masked_key))
print("LLM_MODEL            =", repr(cfg.LLM_MODEL))
print("LLM_TEMPERATURE      =", cfg.LLM_TEMPERATURE)
print("LLM_MAX_OUTPUT_TOKENS=", cfg.LLM_MAX_OUTPUT_TOKENS)
print("LLM_TOP_P            =", cfg.LLM_TOP_P)
print("LLM_TOP_K            =", cfg.LLM_TOP_K)
print("---")
print("ASSISTANT_NAME       =", repr(cfg.ASSISTANT_NAME))
print("ASSISTANT_GREETING   =", repr(cfg.ASSISTANT_GREETING))
print("ASSISTANT_FAREWELL   =", repr(cfg.ASSISTANT_FAREWELL))
print("ASSISTANT_SYSTEM_PROMPT =", repr(cfg.ASSISTANT_SYSTEM_PROMPT))
print("---")
print("LOG_DIRECTORY        =", repr(cfg.LOG_DIRECTORY))
print("LOGGER_NAME          =", repr(cfg.LOGGER_NAME))
print("LOG_LEVEL            =", cfg.LOG_LEVEL)
print("LOG_FORMAT           =", repr(cfg.LOG_FORMAT))
print("LOG_DATE_FORMAT      =", repr(cfg.LOG_DATE_FORMAT))
print("---")
print("STT_PREFERRED_MICS   =", cfg.STT_PREFERRED_MICS)
print("STT_PUSH_TO_TALK_KEY =", repr(cfg.STT_PUSH_TO_TALK_KEY))
print("---")
print("TTS_ENGINE           =", repr(cfg.TTS_ENGINE))
print("TTS_EDGE_VOICE_NAME  =", repr(cfg.TTS_EDGE_VOICE_NAME))
print("TTS_PYTTSX3_VOICES   =", cfg.TTS_PYTTSX3_VOICES)
print("---")
print("AGENT_FACT_SHEET_PATH=", repr(cfg.AGENT_FACT_SHEET_PATH))
print("AGENT_EMBEDDING_MODEL=", repr(cfg.AGENT_EMBEDDING_MODEL))
print("AGENT_TEXT_SPLITTER_CHUNK_SIZE =", cfg.AGENT_TEXT_SPLITTER_CHUNK_SIZE)
print("AGENT_TEXT_SPLITTER_CHUNK_OVERLAP =", cfg.AGENT_TEXT_SPLITTER_CHUNK_OVERLAP)
print("AGENT_RETRIEVER_K    =", cfg.AGENT_RETRIEVER_K)
