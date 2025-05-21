from core.config import load_api_key, init_llm
from core.tools import setup_tools
from agent import init_agent, run_cli, run_tests  # keep run_tests if you still need it

def main():
    api_key = load_api_key()
    llm = init_llm(api_key)
    tools = setup_tools()
    agent = init_agent(llm, tools)

    # Optional: uncomment this line to run tests before launching CLI
    # run_tests(agent)

    run_cli(agent)

if __name__ == "__main__":
    main()
