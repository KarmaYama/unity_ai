#core/config.py

"""
Centralized configuration manager for Zira.
Loads settings from environment variables with sensible defaults.

⚠️ WARNING: Do NOT commit your .env (with secrets) to source control.
In production, use a secrets manager (e.g., Vault or AWS Secrets Manager)
instead of relying solely on a local .env file.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import logging
from pathlib import Path

class Config:
    """
    Loads settings from environment variables (via python-dotenv).
    Validates and canonicalizes file paths to prevent path‐traversal.
    """

    def __init__(self):
        load_dotenv()  # Load variables from .env into os.environ

        # ── API Keys ──────────────────────────────────────────────────────────
        self.GOOGLE_API_KEY = self._get_env_var("GOOGLE_API_KEY", required=True)
        self.OPENWEATHER_API_KEY = self._get_env_var("OPENWEATHER_API_KEY", required=True)

        # ── LLM Configuration ─────────────────────────────────────────────────
        self.LLM_MODEL = self._get_env_var("LLM_MODEL", "gemini-2.5-flash-preview-05-20")

        raw_temp = self._get_env_var("LLM_TEMPERATURE", 0.5)
        try:
            self.LLM_TEMPERATURE = float(raw_temp)
        except ValueError:
            raise RuntimeError("Invalid LLM_TEMPERATURE; must be a float.")

        raw_max_tokens = self._get_env_var("LLM_MAX_OUTPUT_TOKENS", 800)
        try:
            self.LLM_MAX_OUTPUT_TOKENS = int(raw_max_tokens)
        except ValueError:
            raise RuntimeError("Invalid LLM_MAX_OUTPUT_TOKENS; must be an integer.")

        raw_top_p = self._get_env_var("LLM_TOP_P", 0.8)
        try:
            self.LLM_TOP_P = float(raw_top_p)
        except ValueError:
            raise RuntimeError("Invalid LLM_TOP_P; must be a float.")

        raw_top_k = self._get_env_var("LLM_TOP_K", 40)
        try:
            self.LLM_TOP_K = int(raw_top_k)
        except ValueError:
            raise RuntimeError("Invalid LLM_TOP_K; must be an integer.")

        # ── Assistant Persona & Prompts ───────────────────────────────────────
        self.ASSISTANT_NAME = self._get_env_var("ASSISTANT_NAME", "Zira")
        self.ASSISTANT_GREETING = self._get_env_var(
            "ASSISTANT_GREETING",
            "Systems online. I am Zira. How may I assist you today, Alex? Type 'enable voice mode' when you're ready to speak to me."
        )
        self.ASSISTANT_FAREWELL = self._get_env_var("ASSISTANT_FAREWELL", "Going silent. You know where I am if you need me.")
        self.ASSISTANT_SYSTEM_PROMPT = self._get_env_var(
            "ASSISTANT_SYSTEM_PROMPT",
            (
                "You are Zira, a highly sophisticated and intelligent AI. You engage "
                "in conversations naturally, providing thoughtful and intelligent responses. You have a "
                "subtle wit and avoid robotic language. Strive for eloquence and depth."
            )
        )

        # ── Logging Configuration ─────────────────────────────────────────────
        raw_log_dir = self._get_env_var("LOG_DIRECTORY", "log")
        abs_log_dir = os.path.realpath(raw_log_dir)
        project_root = Path(os.getcwd()).resolve()
        if not Path(abs_log_dir).resolve().is_relative_to(project_root):
            raise RuntimeError(f"LOG_DIRECTORY must be inside the project directory: {raw_log_dir}")
        self.LOG_DIRECTORY = abs_log_dir

        self.LOGGER_NAME = self._get_env_var("LOGGER_NAME", "zira_logger")

        log_level_str = self._get_env_var("LOG_LEVEL", "DEBUG").upper()
        self.LOG_LEVEL = getattr(logging, log_level_str, logging.DEBUG)

        self.LOG_FORMAT = self._get_env_var(
            "LOG_FORMAT", "%(asctime)s %(levelname)s: %(message)s"
        )
        self.LOG_DATE_FORMAT = self._get_env_var("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

        # ── Speech-to-Text (STT) Configuration ────────────────────────────────
        stt_mics = self._get_env_var(
            "STT_PREFERRED_MICS",
            "Realtek(R) Audio,HD Audio Mic,Microphone,Hands-Free HF Audio"
        )
        self.STT_PREFERRED_MICS = [m.strip() for m in stt_mics.split(',') if m.strip()]

        self.STT_PUSH_TO_TALK_KEY = self._get_env_var("STT_PUSH_TO_TALK_KEY", "ctrl")

        # ── Text-to-Speech (TTS) Configuration ────────────────────────────────
        self.TTS_ENGINE = self._get_env_var("TTS_ENGINE", "edge")
        self.TTS_EDGE_VOICE_NAME = self._get_env_var("TTS_EDGE_VOICE_NAME", "en-US-JennyNeural")

        tts_voices = self._get_env_var(
            "TTS_PYTTSX3_VOICES",
            "Microsoft Edge,Zira,David"
        )
        self.TTS_PYTTSX3_VOICES = [v.strip() for v in tts_voices.split(',') if v.strip()]
        
        # New: Add TTS_ENABLED flag, default to True based on your requirement
        raw_tts_enabled = self._get_env_var("TTS_ENABLED", "True").lower()
        self.TTS_ENABLED = raw_tts_enabled == "true"


        # ── Agent Tools Configuration ─────────────────────────────────────────
        raw_fact_sheet = self._get_env_var("AGENT_FACT_SHEET_PATH", "data/fact_sheet.txt")
        if os.path.isabs(raw_fact_sheet):
            raise RuntimeError(f"AGENT_FACT_SHEET_PATH must be a relative path under project directory: {raw_fact_sheet}")
        abs_fact_sheet = os.path.realpath(os.path.join(os.getcwd(), raw_fact_sheet))
        if not Path(abs_fact_sheet).resolve().is_relative_to(Path(os.getcwd()).resolve()):
            raise RuntimeError(f"AGENT_FACT_SHEET_PATH must reside in project directory: {raw_fact_sheet}")
        self.AGENT_FACT_SHEET_PATH = raw_fact_sheet

        self.AGENT_EMBEDDING_MODEL = self._get_env_var("AGENT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

        raw_chunk_size = self._get_env_var("AGENT_TEXT_SPLITTER_CHUNK_SIZE", 500)
        try:
            self.AGENT_TEXT_SPLITTER_CHUNK_SIZE = int(raw_chunk_size)
        except ValueError:
            raise RuntimeError("Invalid AGENT_TEXT_SPLITTER_CHUNK_SIZE; must be an integer.")

        raw_chunk_overlap = self._get_env_var("AGENT_TEXT_SPLITTER_CHUNK_OVERLAP", 100)
        try:
            self.AGENT_TEXT_SPLITTER_CHUNK_OVERLAP = int(raw_chunk_overlap)
        except ValueError:
            raise RuntimeError("Invalid AGENT_TEXT_SPLITTER_CHUNK_OVERLAP; must be an integer.")

        raw_retriever_k = self._get_env_var("AGENT_RETRIEVER_K", 5)
        try:
            self.AGENT_RETRIEVER_K = int(raw_retriever_k)
        except ValueError:
            raise RuntimeError("Invalid AGENT_RETRIEVER_K; must be an integer.")
        
        # New agent configuration parameters
        raw_max_iterations = self._get_env_var("AGENT_MAX_ITERATIONS", 10)
        try:
            self.AGENT_MAX_ITERATIONS = int(raw_max_iterations)
        except ValueError:
            raise RuntimeError("Invalid AGENT_MAX_ITERATIONS; must be an integer.")

        self.AGENT_EARLY_STOPPING_METHOD = self._get_env_var("AGENT_EARLY_STOPPING_METHOD", "force")

        self.OPENWEATHER_BASE_URL = self._get_env_var(
            "OPENWEATHER_BASE_URL",
            "https://api.openweathermap.org/data/2.5/weather"
        )
        # Enforce HTTPS
        if not self.OPENWEATHER_BASE_URL.startswith("https://"):
            raise RuntimeError("OPENWEATHER_BASE_URL must begin with 'https://'")

        # ── Bookmarks File Path ───────────────────────────────────────────────
        raw_bookmarks = self._get_env_var("BOOKMARKS_FILE_PATH", "data/bookmarks.json")
        if os.path.isabs(raw_bookmarks):
            raise RuntimeError(f"BOOKMARKS_FILE_PATH must be a relative path under project directory: {raw_bookmarks}")
        abs_bookmarks = os.path.realpath(os.path.join(os.getcwd(), raw_bookmarks))
        if not Path(abs_bookmarks).resolve().is_relative_to(Path(os.getcwd()).resolve()):
            raise RuntimeError(f"BOOKMARKS_FILE_PATH must reside in project directory: {raw_bookmarks}")
        self.BOOKMARKS_FILE_PATH = raw_bookmarks
        
        # Additional root data directory for broader use
        self.ZIRA_DATA_ROOT = self._get_env_var("ZIRA_DATA_ROOT", "data")


    def _get_env_var(self, key: str, default=None, required: bool = False):
        """
        Helper to retrieve an environment variable:
        - If required=True and not found, raises RuntimeError.
        - Otherwise returns os.getenv(key) or the provided default.
        """
        value = os.getenv(key)
        if value is None:
            if required:
                raise RuntimeError(f"Missing required environment variable: {key}")
            return default
        return value

    def init_llm(self) -> ChatGoogleGenerativeAI:
        """
        Initializes and returns the LangChain LLM instance.

        In production, replace static GOOGLE_API_KEY usage with a short‐lived token from a vault.
        """
        if not self.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not set in environment variables.")

        return ChatGoogleGenerativeAI(
            model=self.LLM_MODEL,
            temperature=self.LLM_TEMPERATURE,
            max_output_tokens=self.LLM_MAX_OUTPUT_TOKENS,
            top_p=self.LLM_TOP_P,
            top_k=self.LLM_TOP_K,
            api_key=self.GOOGLE_API_KEY
        )