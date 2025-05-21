# main.py

from core.config import load_api_key, init_llm
from core.tools import setup_tools
from agent import init_agent, run_cli, run_tests

def main():
    """
    Entry point for Unity AI assistant.
    Initializes the language model, tools, and the agent,
    and then starts the CLI interface for interaction.
    """
    # Load environment config (e.g., OpenAI API key)
    api_key = load_api_key()

    # Initialize language model (LLM)
    llm = init_llm(api_key)

    # Set up any tools the agent may use (e.g., web search, calculators, etc.)
    tools = setup_tools()

    # Initialize the Unity ReAct agent with the LLM and tools
    agent = init_agent(llm, tools)

    # Optional: Run diagnostic tests to verify output
    # Uncomment the line below to enable quick agent tests
    # run_tests(agent)

    # Launch the Command-Line Interface for user interaction
    run_cli(agent)

if __name__ == "__main__":
    main()
    print("Unity AI Assistant is starting...")