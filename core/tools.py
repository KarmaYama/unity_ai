from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool

def setup_tools() -> list[Tool]:
    """
    Initialize and return a list of tools available to the Unity AI Agent.
    Currently includes DuckDuckGoSearchRun for web searching.
    """
    search = DuckDuckGoSearchRun()
    return [
        Tool(
            name="DuckDuckGo Search",
            func=search.run,
            description="Useful for searching the web for information."
        )
    ]
