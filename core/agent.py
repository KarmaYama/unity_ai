from langchain.agents import initialize_agent, AgentType

def init_agent(llm, tools):
    """
    Initialize the Unity AI agent with specified LLM and tools.
    Uses a Zero-Shot ReAct-based agent type for flexible task execution.
    """
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
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
    """
    print("🧠 Unity is online. Type 'exit' or 'quit' to stop.")
    while True:
        user_input = input("Unity> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Shutting down.")
            break
        try:
            print(agent.run(user_input))
        except Exception as e:
            print("Error:", e)
