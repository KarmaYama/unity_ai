from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

def load_api_key() -> str:
    load_dotenv()
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GOOGLE_API_KEY in .env")
    return key

# core/config.py
def init_llm(api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-05-20",
        temperature=0,
        max_output_tokens=128,      # smaller JSON payload
        # if supported:
        # max_input_tokens=512,     
        top_p=0.8,
        top_k=40,
        api_key=api_key
    )
