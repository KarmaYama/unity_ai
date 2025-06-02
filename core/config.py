#core/config.py

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import logging # Import logging to use its levels

class Config:
    """
    Centralized configuration manager for Zira.
    Loads settings from environment variables with sensible defaults.
    """
    def __init__(self):
        load_dotenv() # Load environment variables from .env file

        # ── API Keys ──────────────────────────────────────────────────────────
        self.GOOGLE_API_KEY = self._get_env_var("GOOGLE_API_KEY", required=True)

        # ── LLM Configuration ─────────────────────────────────────────────────
        self.LLM_MODEL = self._get_env_var("LLM_MODEL", "gemini-2.5-flash-preview-05-20")
        self.LLM_TEMPERATURE = float(self._get_env_var("LLM_TEMPERATURE", 0.5))
        self.LLM_MAX_OUTPUT_TOKENS = int(self._get_env_var("LLM_MAX_OUTPUT_TOKENS", 800))
        self.LLM_TOP_P = float(self._get_env_var("LLM_TOP_P", 0.8))
        self.LLM_TOP_K = int(self._get_env_var("LLM_TOP_K", 40))

        # ── Assistant Persona & Prompts ───────────────────────────────────────
        self.ASSISTANT_NAME = self._get_env_var("ASSISTANT_NAME", "Zira")
        self.ASSISTANT_GREETING = self._get_env_var(
            "ASSISTANT_GREETING",
            "Hello, I am Zira. Type 'enable voice mode' to use voice commands, or type your command."
        )
        self.ASSISTANT_FAREWELL = self._get_env_var("ASSISTANT_FAREWELL", "Goodbye!")
        self.ASSISTANT_SYSTEM_PROMPT = self._get_env_var(
            "ASSISTANT_SYSTEM_PROMPT",
            (
                "You are Zira, a highly sophisticated and intelligent AI. You engage "
                "in conversations naturally, providing thoughtful and intelligent responses. You have a "
                "subtle wit and avoid robotic language. Strive for eloquence and depth."
            )
        )

        # ── Logging Configuration ─────────────────────────────────────────────
        self.LOG_DIRECTORY = self._get_env_var("LOG_DIRECTORY", "log")
        self.LOGGER_NAME = self._get_env_var("LOGGER_NAME", "zira_logger")
        # Map string log levels to logging module constants
        log_level_str = self._get_env_var("LOG_LEVEL", "DEBUG").upper()
        self.LOG_LEVEL = getattr(logging, log_level_str, logging.DEBUG)
        self.LOG_FORMAT = self._get_env_var(
            "LOG_FORMAT", "%(asctime)s %(levelname)s: %(message)s"
        )
        self.LOG_DATE_FORMAT = self._get_env_var("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

        # ── Speech-to-Text (STT) Configuration ────────────────────────────────
        self.STT_PREFERRED_MICS = self._get_env_var(
            "STT_PREFERRED_MICS",
            "Realtek(R) Audio,HD Audio Mic,Microphone,Hands-Free HF Audio"
        ).split(',') # Split comma-separated string into a list
        self.STT_PUSH_TO_TALK_KEY = self._get_env_var("STT_PUSH_TO_TALK_KEY", "ctrl")

        # ── Text-to-Speech (TTS) Configuration ────────────────────────────────
        self.TTS_ENGINE = self._get_env_var("TTS_ENGINE", "edge") # 'edge' or 'pyttsx3'
        self.TTS_EDGE_VOICE_NAME = self._get_env_var("TTS_EDGE_VOICE_NAME", "en-US-JennyNeural")
        self.TTS_PYTTSX3_VOICES = self._get_env_var(
            "TTS_PYTTSX3_VOICES",
            "Microsoft Edge,Zira,David"
        ).split(',') # Split comma-separated string into a list

        # ── Agent Tools Configuration ─────────────────────────────────────────
        self.AGENT_FACT_SHEET_PATH = self._get_env_var("AGENT_FACT_SHEET_PATH", "fact_sheet.txt")
        self.AGENT_EMBEDDING_MODEL = self._get_env_var("AGENT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.AGENT_TEXT_SPLITTER_CHUNK_SIZE = int(self._get_env_var("AGENT_TEXT_SPLITTER_CHUNK_SIZE", 500))
        self.AGENT_TEXT_SPLITTER_CHUNK_OVERLAP = int(self._get_env_var("AGENT_TEXT_SPLITTER_CHUNK_OVERLAP", 100))
        self.AGENT_RETRIEVER_K = int(self._get_env_var("AGENT_RETRIEVER_K", 5))

    def _get_env_var(self, key: str, default=None, required: bool = False):
        """Helper to get environment variable with default and optional requirement."""
        value = os.getenv(key)
        if value is None:
            if required:
                raise RuntimeError(f"Missing required environment variable: {key}")
            return default
        return value

    def init_llm(self) -> ChatGoogleGenerativeAI:
        """Initializes and returns the LangChain LLM instance."""
        if not self.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not set in environment variables.")

        llm = ChatGoogleGenerativeAI(
            model=self.LLM_MODEL,
            temperature=self.LLM_TEMPERATURE,
            max_output_tokens=self.LLM_MAX_OUTPUT_TOKENS,
            top_p=self.LLM_TOP_P,
            top_k=self.LLM_TOP_K,
            api_key=self.GOOGLE_API_KEY
        )
        return llm

# Instantiate the config globally or pass it around as needed
# config = Config() # You might instantiate it once in main.py and pass it down.
