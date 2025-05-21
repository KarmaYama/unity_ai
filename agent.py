from langchain.agents import initialize_agent, AgentType
from langchain_core.language_models import BaseChatModel
from langchain.tools import Tool
from core.db import log_case
import json
import warnings
import time

SYSTEM_PROMPT = """
You are Unity, a JSON-only multilingual AI assistant. You MUST respond strictly in the following JSON format, with no greeting, text, explanation, or formatting:

{
  "issue": "<brief summary of user's issue>",
  "severity": <1 to 5>,
  "next_step": "<recommended action>"
}

Rules:
- ❌ No greetings, no commentary, no explanation.
- ✅ Output only a single valid JSON object. No markdown.
- ✅ Always fill all three fields.
- Set severity:
  - 1: General question
  - 3: Housing/employment issues
  - 4–5: Emergency/legal/health (e.g., police, deportation, GBV, assault)
- If unsure, default to severity 2.
- If the user's input is not a specific issue requiring categorization and a next step, try to summarize the input as the "issue" and set a severity of 1 with a generic "next_step" like "Acknowledge the query."

Examples of valid output:
{"issue": "permit renewal question", "severity": 1, "next_step": "send self-service FAQ link"}
{"issue": "user asked what you are", "severity": 1, "next_step": "Acknowledge the query."}

Respond ONLY with valid JSON. Do NOT say anything else. No greetings. No “Hello.” Just JSON.
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