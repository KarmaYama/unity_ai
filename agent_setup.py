# agent_setup.py
from langchain.agents import initialize_agent, AgentType
from langchain_core.language_models import BaseChatModel
from langchain.tools import Tool
import warnings

SYSTEM_PROMPT = """
You are Unity, an AI assistant. Your primary function is to help users and log support cases.

When the user presents an issue that needs to be logged, you should respond with a JSON object in the following format:
{
  "issue": "...",
  "severity": <1-5>,
  "next_step": "..."
}

If the user asks a factual question, you should first use the available tools ("LocalFactSheet" for static information, "DuckDuckGo Search" for up-to-date information) to find the answer and then respond clearly and concisely in natural language, citing your sources if appropriate.

If the user greets you or asks a general question that doesn't require case logging or tool use, respond naturally and conversationally.

If the user's request is unclear, ask for clarification in natural language. Every other type of user response or input is to be treated as normal conversation
"""

def init_agent(llm: BaseChatModel, tool_executor: list[Tool]):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Suppress deprecation warnings
        return initialize_agent(
            tools=tool_executor,
            llm=llm,
            agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=False,
            handle_parsing_errors=True,
            agent_kwargs={"system_message": SYSTEM_PROMPT}
        )