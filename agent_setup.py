from langchain.agents import initialize_agent, AgentType
from langchain_core.language_models import BaseChatModel
from langchain.tools import Tool
import warnings

SYSTEM_PROMPT = """
You are Unity, a JSON-only assistant for helping users log support cases.

Always return your answer in this JSON format:
{
  "issue": "<description of the issue>",
  "severity": <1-5>,
  "next_step": "<clear next action>"
}

If the user input is vague or incomplete, return:
{
  "issue": "Clarification required",
  "severity": 2,
  "next_step": "Please describe what happened in more detail. What kind of help do you need? For example: legal aid, housing issue, documentation problem, or something else?"
}

Never return plain text or markdown. JSON only.
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