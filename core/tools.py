# core/tools.py
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.prebuilt import ToolExecutor

def setup_tools():
    """
    Returns a ToolExecutor containing all tools for LangGraph agents.
    """
    search = DuckDuckGoSearchRun()
    tools = [
        {
            "name": "DuckDuckGo Search",
            "description": "Useful for searching the web for information.",
            "func": search.run,
        }
    ]
    return ToolExecutor(tools)
