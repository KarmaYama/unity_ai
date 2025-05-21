from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool
from langgraph import ToolExecutor  

def setup_tools() -> ToolExecutor:
    """
    Initialize and return a ToolExecutor with the available tools.
    """
    search = DuckDuckGoSearchRun()
    tools = [
        Tool(
            name="DuckDuckGo Search",
            func=search.run,
            description="Useful for searching the web for information."
        )
    ]
    return ToolExecutor(tools)
