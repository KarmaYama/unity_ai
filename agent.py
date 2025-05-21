from langchain.agents import initialize_agent, AgentType
from langchain_core.language_models import BaseChatModel
from langchain.tools import Tool
from core.db import log_case
import json
import warnings
import time

SYSTEM_PROMPT = """
You are Unity, a JSON-only multilingual AI assistant designed to process user queries and respond EXCLUSIVELY with a single, valid JSON object.

The JSON object MUST conform to the following schema:
{
  "issue": "<brief summary of the user's issue>",
  "severity": <integer between 1 and 5>",
  "next_step": "<recommended action or information>"
}

Severity Levels:
- 1: For general questions or informational requests.
- 3: For issues related to housing or employment.
- 4: For urgent situations like potential legal issues or safety concerns.
- 5: For emergencies involving immediate danger, health crises, or severe legal problems.
- If the issue's severity is uncertain, default to 2.

Example Responses:
{"issue": "How do I find a job?", "severity": 1, "next_step": "Provide links to job search websites."}
{"issue": "I am being evicted.", "severity": 3, "next_step": "Suggest contacting a tenant rights organization."}
{"issue": "I was assaulted.", "severity": 5, "next_step": "Advise calling the police immediately and seeking medical help."}
{"issue": "What are your capabilities?", "severity": 1, "next_step": "State that you process user queries to identify issues, their severity, and recommend next steps."}

You MUST NOT include any introductory phrases, greetings, explanations, or any text outside of the single JSON object. Your entire response should be just the JSON.
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

def run_tests(agent):
    queries = [
        "I was arrested by immigration officers and I need help.",
        "How can I renew my asylum seeker permit in Cape Town?",
        "My landlord kicked me out because I’m a refugee.",
        "what are you?"
    ]
    for i, q in enumerate(queries, 1):
        try:
            result = agent.invoke({"input": q})
            print(f"[Test {i}] {q}\n→ {result['output']}\n")
        except Exception as e:
            print(f"[Test {i}] Failed: {e}")


def run_cli(agent):
    print("Unity: Hello, how can I help you today? Type 'exit' to quit.")
    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe. 👋")
            break
        try:
            response = agent.invoke({"input": user_input})
            raw = response.get("output", "").strip()
            print("Raw Result:", raw)
            try:
                data = json.loads(raw)
                log_case(data["issue"], int(data["severity"]), data["next_step"])
                print("Case logged.\n")
            except json.JSONDecodeError:
                print("Error: Could not parse agent output as JSON.\n")
        except Exception as e:
            print("Runtime error:", e)
        time.sleep(1) # Adding a small delay to respect rate limits

if __name__ == "__main__":
    # Example of how to initialize and run the CLI directly from this file
    from core.config import load_api_key, init_llm
    from core.tools import setup_tools

    api_key = load_api_key()
    llm = init_llm(api_key)
    tools = setup_tools()
    agent = init_agent(llm, tools)
    # run_tests(agent) # Uncomment to run tests with the new prompt
    run_cli(agent)