from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import SystemMessagePromptTemplate
import json
from core.db import log_case

SYSTEM_PROMPT = """
You are Unity, an AI assistant for Africa Unite peer educators.
Return ONLY strict JSON:
{
  "issue": "...",
  "severity": 1-5,
  "next_step": "..."
}
No extra explanation or commentary.
"""

def init_agent(llm, tools):
    """
    Initialize the Unity AI agent using LangGraph's ReAct agent setup.
    """
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        system_message=SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT)
    )
    return agent

def run_tests(agent):
    """
    Run a series of predefined queries to verify agent functionality.
    """
    queries = [
        "What is the capital of France?",
        "Search for the latest news on AI.",
        "Explain the significance of the Turing test in AI."
    ]
    for i, q in enumerate(queries, 1):
        try:
            print(f"[Test {i}] {q}\n→ {agent.invoke({'input': q})['output']}\n")
        except Exception as e:
            print(f"Test {i} failed: {e}")

def run_cli(agent):
    """
    Start a simple CLI interface for interacting with the Unity AI Agent.
    Expects strict JSON output and logs structured cases to SQLite.
    """
    print("Unity is online. Type 'exit' to quit.")
    while True:
        user_input = input("Unity> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("👋 Shutting down.")
            break
        try:
            result = agent.invoke({"input": user_input})
            output = result.get("output", "")
            print(output)

            data = json.loads(output)
            log_case(data["issue"], int(data["severity"]), data["next_step"])
            print("Case logged.\n")
        except Exception as e:
            print("Error:", e)
