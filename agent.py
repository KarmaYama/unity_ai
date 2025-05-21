from langgraph.prebuilt import create_react_agent
from langgraph import AgentExecutor
from langchain_core.prompts import SystemMessagePromptTemplate
from core.db import log_case

SYSTEM_PROMPT = """
You are Unity, a multilingual AI assistant for Africa Unite peer educators and field staff.
Your job is to quickly assess incoming user messages from migrants, asylum seekers, or refugees.

Return ONLY strict JSON in the following format:
{
  "issue": "<summarized issue in 5-15 words>",
  "severity": <1 (low) to 5 (critical)>,
  "next_step": "<recommended action, e.g., 'refer to legal clinic', 'escalate to caseworker', 'send FAQ link'>"
}

Guidelines:
- Do NOT include any commentary, explanation, or non-JSON output.
- Use plain language.
- If a message involves keywords like "arrest", "deportation", "rape", "GBV", or "police", set severity to 4 or 5 and recommend escalation.
- If the message is a common question (e.g., how to renew asylum papers), set severity to 1 or 2 and suggest a self-service step.
- Be language-neutral; extract intent even if in French or Shona.

Respond with clean, parseable JSON only.
"""


def init_agent(llm, tool_executor):
    """
    Initializes the LangGraph-based Unity AI Agent using the ReAct agent template.
    """
    agent_node = create_react_agent(
        system=SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
        tools=tool_executor,
        prompt=None,  # Optional, you can use your own PromptTemplate
    )
    
    return AgentExecutor(agent=agent_node, tools=tool_executor)

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
            print(f"[Test {i}] {q}\n→ {agent.invoke({'input': q})}\n")
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
            print(result)

            data = json.loads(result)
            log_case(data["issue"], int(data["severity"]), data["next_step"])
            print("Case logged.\n")
        except Exception as e:
            print("Error:", e)
