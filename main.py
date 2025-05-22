from core.config import load_api_key, init_llm
from core.tools import setup_tools, build_memory
from agent_cli import run_cli
from agent_setup import init_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from colorama import Fore
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
import time

BASE_GENERATION_SYSTEM_PROMPT = """
You are Unity, a concise assistant with access to a refugee-rights fact sheet.
Answer questions only from the fact sheet. Before replying, pause with a short “thinking…” animation.
"""

BASE_REFLECTION_SYSTEM_PROMPT = """
Critique the previous answer: is it accurate, helpful, and directly drawn from the fact sheet?
If yes, respond with "<OK>". Otherwise, give one clear suggestion to improve.
"""


class ReflectionAgent:
    def __init__(self, llm: ChatGoogleGenerativeAI, memory_retriever, n_reflect_steps=1):
        self.llm = llm
        self.retriever = memory_retriever
        self.n_reflect_steps = n_reflect_steps

    def _invoke_llm(self, messages):
        # ensure messages have content
        for m in messages:
            if not getattr(m, "content", "").strip():
                print(Fore.RED + "[ERROR] Empty message passed to LLM:", m)
                raise ValueError("Empty message passed to LLM")
        # debug print full prompt
        prompt_preview = " | ".join(m.content.replace("\n", " ")[:200] for m in messages)
        print(Fore.YELLOW + f"[DEBUG] Prompt to LLM: {prompt_preview}...")
        resp = self.llm.invoke(messages)
        content = getattr(resp, "content", None)
        if not content or not content.strip():
            print(Fore.RED + "[ERROR] LLM returned empty response.")
            return None
        return content

    def generate(self, prompt_messages):
        resp = self._invoke_llm(prompt_messages)
        if resp is None:
            return "Sorry, I couldn't find that information."
        return resp

    def reflect(self, previous: str) -> None:
        msgs = [
            SystemMessage(content=BASE_REFLECTION_SYSTEM_PROMPT.strip()),
            HumanMessage(content=previous.strip())
        ]
        critique = self._invoke_llm(msgs)
        if critique and "<OK>" not in critique:
            print(Fore.MAGENTA + "Reflection suggestion:", critique)

    def run(self, query: str) -> str:
        # Retrieve relevant fact-sheet chunks
        docs = self.retriever.invoke(query)
        if not docs:
            print(Fore.RED + "Unity: No relevant facts found. Try rephrasing.")
            return "I couldn't find relevant facts."

        # Combine and debug-print memory
        memory = "\n\n".join(d.page_content for d in docs)
        print(Fore.YELLOW + f"[DEBUG] Retrieved memory (first 500 chars):\n{memory[:500]}{'...' if len(memory)>500 else ''}\n")

        # Simulate thinking
        for dots in ("thinking.", "thinking..", "thinking..."):
            print(Fore.CYAN + f"Unity: {dots}")
            time.sleep(0.3)

        # Build main prompt
        system = SystemMessage(content=BASE_GENERATION_SYSTEM_PROMPT.strip())
        human = HumanMessage(content=f"Memory:\n{memory}\n\nQuestion: {query}")
        answer = self.generate([system, human])
        print(Fore.BLUE + "Unity:", answer)

        # Reflection step
        try:
            self.reflect(answer)
        except Exception as e:
            print(Fore.RED + f"Reflection failed: {e}")

        return answer


def main():
    api_key = load_api_key()
    llm = init_llm(api_key)

    # Build neural memory retriever
    memory_retriever = build_memory(api_key)

    # Tools for other queries
    tools = setup_tools(api_key, llm, return_retriever_only=False)

    reflection_agent = ReflectionAgent(llm, memory_retriever)
    agent = init_agent(llm, tools)

    run_cli(agent, reflection_agent=reflection_agent)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(Fore.RED + f"Fatal error → {e}")
    finally:
        print(Fore.RESET + "Exiting Unity AI.")
        print(Fore.RESET + "Goodbye!")