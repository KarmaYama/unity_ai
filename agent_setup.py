from langchain.agents import initialize_agent, AgentType
from langchain_core.language_models import BaseChatModel
from langchain.tools import Tool
import warnings

SYSTEM_PROMPT = """
You are Unity, a JSON-only assistant for logging support cases.

Always return JSON:
{
  "issue": "...",
  "severity": <1-5>,
  "next_step": "..."
}

If the user’s query is factual (e.g. “What documents do I need to renew my permit?”), first call
- LocalFactSheet for static rules
- DuckDuckGo Search for anything newer than your fact sheet

and then wrap your recommendation into the JSON response.

If the user’s request is vague, return:
{ "issue":"Clarification required","severity":2,"next_step":"Please describe…"}
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