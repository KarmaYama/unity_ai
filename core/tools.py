from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool

def setup_tools():
    search = DuckDuckGoSearchRun()
    tools = [
        Tool(
            name="DuckDuckGo Search",
            func=search.run,
            description="Use this tool to search the web for current information."
        )
    ]
    return tools
