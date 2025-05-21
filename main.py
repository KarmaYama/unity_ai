from core.config import load_api_key, init_llm
from core.tools import setup_tools
from core.agent import init_agent, run_tests, run_cli

def main():
    api_key = load_api_key()
    llm = init_llm(api_key)
    tools = setup_tools()
    agent = init_agent(llm, tools)
    run_tests(agent)
    run_cli(agent)

if __name__ == "__main__":
    main()
