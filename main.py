# main.py
from core.config import load_api_key, init_llm
from core.tools import setup_tools
from agent import init_agent, run_cli, run_tests

def main():
    api_key = load_api_key()
    llm = init_llm(api_key)
    tools = setup_tools()  # Returns ToolExecutor in LangGraph
    agent = init_agent(llm, tools)

    # Optional testing
    # run_tests(agent)

    run_cli(agent)

if __name__ == "__main__":
    main()
# This script initializes the Unity AI agent and starts a CLI for user interaction.
# It loads the API key, initializes the LLM, sets up tools, and runs the agent.
# The script is designed to be run as a standalone program.
# It also includes optional testing functionality to verify the agent's responses.
# The agent is designed to handle user queries and log cases to a SQLite database.
# The script is modular, with separate functions for loading configuration, initializing the agent, and running tests.
# The main function orchestrates the initialization and execution of the agent.
# The script is structured to allow for easy expansion and modification.
# The use of environment variables for API keys enhances security and flexibility.
# The script is designed to be user-friendly, with clear prompts and error handling.
# The CLI interface allows for real-time interaction with the agent.