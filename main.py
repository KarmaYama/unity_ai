# main.py
from core.config import load_api_key, init_llm
from core.tools import setup_tools
from agent_setup import init_agent
from agent_cli import run_cli

def main():
    api_key = load_api_key()
    llm     = init_llm(api_key)
    tools   = setup_tools(api_key, llm)
    agent   = init_agent(llm, tools)
    run_cli(agent)

if __name__ == "__main__":
    main()
