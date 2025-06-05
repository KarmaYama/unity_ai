# core/handler_graph.py

import re
from typing import Any, Dict, TypedDict, Annotated

from colorama import Fore, Style
from google.api_core.exceptions import TooManyRequests

# ── Import the core “graph” classes from langgraph ──
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import (
    ToolNode, # This one is generally stable and used for tool execution
)

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage

# For state persistence (checkpointer)
from langgraph.checkpoint.memory import MemorySaver

from core.utils.data_sanitizer import scrub_sensitive_data, contains_control_chars
from core.tts import speak
from core.config import Config # Import Config to use its TTS_ENABLED


# Define the State for our LangGraph.
class AgentState(TypedDict):
    """
    Represents the state of our agent's graph.
    Messages are the core conversational history.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    last_parse_status: str # Added to store the result of parsing for conditional routing

class GraphAgent:
    """
    A LangGraph‐based agent that:
      1) Processes user input, adds to state messages
      2) Calls Gemini (LLM) to decide “Final Answer” or “Action:<tool>”
      3) If “Final Answer”, the graph finishes (response is printed).
      4) If “Action”, calls the ToolExecutor node.
      5) ToolExecutor output is automatically added to messages, and loop back to LLM.
      6) Catches TooManyRequests (rate‑limit) and short‑circuits to an error response
    """

    def __init__(
        self,
        llm,
        agent_tools: list,
        logger,
        config: Config, # Type hint for clarity
        voice_flag_ref: dict,
    ):
        """
        Args:
          llm: A LangChain LLM instance (Gemini, OpenAI, etc.)
          agent_tools: List of langchain.tools.Tool objects (name/func/description)
          logger: A Python logger
          config: Your Config object (for prompts, ASSISTANT_NAME, etc.)
          voice_flag_ref: Shared dict {"enabled": bool} for toggling TTS (user input)
        """
        self.llm = llm
        self.agent_tools = agent_tools
        self.logger = logger
        self.config = config # Store config for TTS_ENABLED access
        self.voice_flag_ref = voice_flag_ref # This is for USER voice input, not Zira's speech

        # Bind tools to the LLM for tool calling capabilities.
        self.llm_with_tools = self.llm.bind_tools(self.agent_tools)

        # ── Build the planning prompt ──
        self.planning_prompt_template = self._build_planning_prompt_template()

        # ── Initialize the StateGraph with our defined AgentState ──
        self.graph_builder = StateGraph(AgentState)

        # ── Define Nodes ──
        self.graph_builder.add_node("UserInputProcessor", self._user_input_processor_node)
        self.graph_builder.add_node("LLMPlanning", self._call_llm_node)
        self.graph_builder.add_node("ParseAction", self._parse_and_route_action_node)
        self.graph_builder.add_node("Respond", self._respond_to_user)
        
        # Instantiate ToolNode once with the list of tools
        self.graph_builder.add_node("ToolExecutor", ToolNode(tools=self.agent_tools))


        # ── Define Edges (Transitions) ──

        # 1. Entry Point: From START to UserInputProcessor
        self.graph_builder.add_edge(START, "UserInputProcessor")
        
        # 2. UserInputProcessor -> LLMPlanning
        self.graph_builder.add_edge("UserInputProcessor", "LLMPlanning")

        # 3. LLMPlanning -> Conditional routing based on _is_final_answer method
        self.graph_builder.add_conditional_edges(
            "LLMPlanning", # From node
            self._is_final_answer, # Condition function (returns name of next node or END)
            {
                "respond": "Respond", # If _is_final_answer returns "respond"
                "continue": "ParseAction" # If _is_final_answer returns "continue"
            }
        )
        
        # 4. ParseAction -> Conditional routing based on the 'last_parse_status' in state
        # The _parse_and_route_action_node now updates the state, and this conditional reads it.
        self.graph_builder.add_conditional_edges(
            "ParseAction", # From node
            lambda state: state.get("last_parse_status", "respond_with_error"), # Condition function
            {
                "tool_call_found": "ToolExecutor", # If tool call was parsed
                "respond_with_error": "Respond" # If parsing failed or no valid tool call
            }
        )

        # 5. After ToolExecutor -> LLMPlanning (for re-evaluation)
        self.graph_builder.add_edge("ToolExecutor", "LLMPlanning")
        
        # 6. Set the end point of the graph
        self.graph_builder.add_edge("Respond", END)

        # Compile the graph with a checkpointer for memory persistence
        self.checkpointer = MemorySaver()
        self.compiled_graph = self.graph_builder.compile(
            checkpointer=self.checkpointer
        )


    def _build_planning_prompt_template(self) -> str:
        """
        Constructs the prompt template for the planning node. It instructs Gemini
        to choose either a Final Answer or Action:<tool> with Action Input:<args>.
        """
        tool_list = "\n".join(f"{t.name}: {t.description}" for t in self.agent_tools)
        prompt = (
            self.config.ASSISTANT_SYSTEM_PROMPT
            + "\n\n"
            # REMOVED custom "Action: <tool>" format instructions.
            # LangChain's bind_tools will handle the tool call format in AIMessage.tool_calls.
            # We only prompt for Final Answer here if we want to ensure it uses that.
            # If you still want a custom syntax, you'll need to parse AIMessage.content
            # in _parse_and_route_action_node to extract it, and ignore .tool_calls.
            # But the recommended way with bind_tools is to rely on .tool_calls.
            + "Based on the conversation so far, decide whether to provide a Final Answer, or to use an available tool.\n\n"
            + "Available tools:\n"
            + f"{tool_list}\n\n"
            + "Respond with a Final Answer: <your answer> if you are done, or by calling a tool if needed."
        )
        return prompt

    async def _handle_llm_error(self, error: Exception) -> str:
        """
        If the LLM raises TooManyRequests (Gemini rate limit), return a short error
        message. Otherwise, return a generic fallback.
        """
        if isinstance(error, TooManyRequests):
            return "Error: Gemini is being rate-limited. Please try again in a few seconds."
        self.logger.error(f"LLM error: {error}", exc_info=True)
        return "Error: an unexpected issue occurred in the reasoning engine."

    # --- Node Implementations ---

    def _user_input_processor_node(self, state: AgentState) -> AgentState:
        """
        Processes initial user input from the state. Adds it as a HumanMessage
        to the state's messages list if it's not already there.
        """
        # This node expects 'state' to already contain the initial HumanMessage from 'run'.
        # It's primarily a pass-through here, or a place for initial sanitization of the message content.
        # The 'run' method now passes the correctly formatted initial state.
        self.logger.debug(f"UserInputProcessor received state: {state}")
        # Add any additional sanitization here if needed beyond what's done in 'run'
        return state


    async def _call_llm_node(self, state: AgentState) -> AgentState:
        """
        Invokes the LLM with the current chat history and planning prompt.
        Updates the state with the LLM's response.
        """
        messages = state["messages"]
        
        # Prepare messages for the LLM. The planning_prompt is effectively a system message.
        # The planning_prompt is a HumanMessage because the LLM is expected to respond based on it.
        llm_input_messages = [HumanMessage(content=self.planning_prompt_template)] + messages
        
        try:
            response = await self.llm_with_tools.ainvoke(llm_input_messages)
            return {"messages": [response]}
        
        except TooManyRequests as e:
            error_msg = self._handle_llm_error(e)
            return {"messages": [AIMessage(content=error_msg)]}
        except Exception as e:
            error_msg = self._handle_llm_error(e)
            return {"messages": [AIMessage(content=error_msg)]}

    def _is_final_answer(self, state: AgentState) -> str:
        """
        Conditional logic for routing after LLMPlanning.
        Checks the last message from the LLM to see if it's a final answer or a tool call.
        Returns "respond" if it's a final answer, or "continue" if it's a tool call (or needs more processing).
        """
        messages = state["messages"]
        if not messages:
            self.logger.warning("No messages in state for final answer check. Defaulting to continue.")
            return "continue"
        
        last_message = messages[-1]
        
        # If the LLM has called a tool, it's not a final answer yet.
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            self.logger.debug(f"LLM produced tool_calls. Routing to ParseAction. State: {state}")
            return "continue" # Route to ParseAction
        
        # If it's an AIMessage without tool_calls, check for "Final Answer:"
        if isinstance(last_message, AIMessage):
            content = last_message.content
            if content and str(content).strip().lower().startswith("final answer:"):
                self.logger.debug(f"LLM produced final answer. Routing to Respond. State: {state}")
                return "respond" # Route to Respond
        
        # If it's anything else (e.g., ToolMessage, or a malformed AIMessage), treat as needing more processing
        # or as an error that needs to be handled by ParseAction.
        self.logger.warning(f"Unexpected message type or content for final answer check: {type(last_message).__name__}. Content: {last_message.content if hasattr(last_message, 'content') else ''}. Routing to continue.")
        return "continue"


    def _parse_and_route_action_node(self, state: AgentState) -> AgentState: # Node must return AgentState
        """
        Node function to parse the LLM's output for an action (tool call).
        Updates the state with a 'last_parse_status' indicating if a tool call was found or an error occurred.
        Returns the updated state.
        """
        messages = state["messages"]
        if not messages:
            self.logger.error("ParseAction node received empty messages state. Setting status to respond_with_error.")
            state["messages"].append(AIMessage(content="Error: No LLM output to parse for action."))
            state["last_parse_status"] = "respond_with_error"
            return state
            
        last_message = messages[-1]

        # Langchain tools are called via message.tool_calls (list of dicts)
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            if last_message.tool_calls:
                self.logger.debug(f"Tool call detected by LLM. Setting status to tool_call_found.")
                state["last_parse_status"] = "tool_call_found"
                return state # Return the state
        
        # Fallback if no tool calls were detected in AIMessage, or if last message wasn't AIMessage
        self.logger.error(f"ParseAction: No valid tool call found in last LLM message: {last_message.content if hasattr(last_message, 'content') else str(last_message)}. Setting status to respond_with_error.")
        state["messages"].append(AIMessage(content="Error: The agent could not determine a valid tool action or final answer."))
        state["last_parse_status"] = "respond_with_error"
        return state # Return the state


    async def _respond_to_user(self, state: AgentState):
        """
        Node function to strip “Final Answer:” if present and prints + (optionally) speaks the reply.
        Takes the full state. This is the final step before the graph ends.
        """
        messages = state["messages"]
        if not messages:
            self.logger.warning("Respond node received empty messages state for final response.")
            cleaned = "I'm not sure how to respond."
        else:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                cleaned = re.sub(r"(?i)^Final Answer:\s*", "", last_message.content).strip()
            elif isinstance(last_message, HumanMessage):
                self.logger.warning(f"Respond node received a HumanMessage as last message: {last_message.content}. Agent flow might be incomplete.")
                cleaned = "I'm experiencing an internal communication issue."
            elif isinstance(last_message, ToolMessage):
                self.logger.warning(f"Respond node received a ToolMessage as last message: {last_message.content}. Agent flow might be incomplete and ended unexpectedly after a tool.")
                cleaned = f"Tool result processed, but no final answer: {last_message.content}"
            else:
                cleaned = str(last_message)

            if contains_control_chars(cleaned):
                cleaned = "[Response contained invalid characters and was sanitized.]"
                self.logger.warning("Sanitized response due to control characters.")

        print(Fore.CYAN + f"{self.config.ASSISTANT_NAME}: {cleaned}" + Style.RESET_ALL)
        # Zira should always speak if TTS is enabled in config, regardless of user voice input mode.
        if self.config.TTS_ENABLED: # Check config's TTS_ENABLED, not voice_flag_ref
            await speak(cleaned)

    async def run(self, user_input: str, thread_id: str = "default_user"):
        """
        Top‑level entry: run the graph with user_input.
        Uses a thread_id for checkpointing to maintain conversation history.
        """
        if contains_control_chars(user_input):
            msg = "Invalid input detected—please use standard characters only."
            print(Fore.RED + msg + Style.RESET_ALL)
            if self.config.TTS_ENABLED: # Use config.TTS_ENABLED for this too
                await speak(msg)
            return

        try:
            # Initial input to the graph must conform to AgentState
            initial_state = {"messages": [HumanMessage(content=user_input)]}
            
            async for s in self.compiled_graph.astream(
                initial_state, # Pass the structured initial state
                config={"configurable": {"thread_id": thread_id}, "recursion_limit": self.config.AGENT_MAX_ITERATIONS}
            ):
                # This loop processes intermediate steps if needed, but 'pass' is fine for just running to completion.
                # If you want to see intermediate states, you can print 's' here.
                pass

            self.logger.debug(f"Graph execution complete for thread_id: {thread_id}")
        except Exception as e:
            self.logger.error(f"Error during graph execution for thread_id {thread_id}: {e}", exc_info=True)
            error_message = "An error occurred while processing your request. Please try again."
            print(Fore.RED + error_message + Style.RESET_ALL)
            if self.config.TTS_ENABLED: # Use config.TTS_ENABLED for this too
                await speak(error_message)