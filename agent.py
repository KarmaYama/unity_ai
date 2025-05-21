from langchain.agents import initialize_agent, AgentType
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
    Initialize the Unity AI agent with specified LLM and tools.
    Uses a Zero-Shot ReAct-based agent with a structured JSON prompt.
    """
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        system_message=SYSTEM_PROMPT
    )

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
            print(f"[Test {i}] {q}\n→ {agent.run(q)}\n")
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
            response = agent.run(user_input)
            print(response)

            data = json.loads(response)
            log_case(data["issue"], int(data["severity"]), data["next_step"])
            print("Case logged.\n")
        except Exception as e:
            print("Error:", e)
