# core/command_dispatcher.py

import re
from colorama import Fore, Style

from core.handler_system import SystemHandler
from core.handler_graph import GraphAgent


class CommandDispatcher:
    """
    Routes each incoming user command:
      1) First tries SystemHandler (voice toggles, help, bookmarks, open/close, weather, search).
      2) If SystemHandler returns False, runs the LangGraph agent (GraphAgent.run).
    """

    def __init__(
        self,
        llm,
        tools: dict,
        agent_tools: list,
        search_tool,
        logger,
        voice_flag_ref: dict,
        config,
    ):
        self.system = SystemHandler(
            tools=tools,
            search_tool=search_tool,
            logger=logger,
            voice_flag_ref=voice_flag_ref,
            config=config,
        )

        self.graph_agent = GraphAgent(
            llm=llm,
            agent_tools=agent_tools,
            logger=logger,
            config=config,
            voice_flag_ref=voice_flag_ref,
        )

    async def process_command(self, raw_text: str) -> None:
        """
        Entry point for every user input. Normalizes whitespace, then:
         - If SystemHandler.try_handle(...) returns True → done.
         - Otherwise → GraphAgent.run(raw_text).
        """
        sanitized = re.sub(r"\s+", " ", raw_text).strip()
        print(Fore.MAGENTA + f"[Dispatcher] Received: {sanitized}" + Style.RESET_ALL)

        handled = await self.system.try_handle(sanitized)
        if handled:
            return

        await self.graph_agent.run(sanitized)
