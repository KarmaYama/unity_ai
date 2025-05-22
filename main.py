# main.py
from core.config import load_api_key, init_llm
from core.tools import setup_tools
from agent_cli import run_cli
from agent_setup import init_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from colorama import Fore
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
    def __init__(self, llm: ChatGoogleGenerativeAI, n_reflect_steps=1):
        self.llm = llm
        self.n_reflect_steps = n_reflect_steps

    def _invoke_llm(self, messages):
        # guard & debug
        for m in messages:
            if not getattr(m, "content", "").strip():
                raise ValueError("Empty message passed to LLM")
        print(Fore.YELLOW + f"[DEBUG] → {[(type(m).__name__, m.content[:60]+'…') for m in messages]}")
        resp = self.llm.invoke(messages)
        if not getattr(resp, "content", "").strip():
            raise RuntimeError("LLM returned empty")
        return resp.content

    def generate(self, user_prompt: str) -> str:
        msgs = [
            SystemMessage(content=BASE_GENERATION_SYSTEM_PROMPT.strip()),
            HumanMessage(content=user_prompt.strip())
        ]
        return self._invoke_llm(msgs)

    def reflect(self, previous: str) -> str:
        msgs = [
            SystemMessage(content=BASE_REFLECTION_SYSTEM_PROMPT.strip()),
            HumanMessage(content=previous.strip())
        ]
        return self._invoke_llm(msgs)

    def run(self, query: str, context: str) -> str:
        # simulate thinking…
        for dots in ("thinking.", "thinking..", "thinking..."):
            print(Fore.CYAN + f"Unity: {dots}")
            time.sleep(0.3)

        prompt = f"Context:\n{context}\n\nQuestion: {query}"
        answer = self.generate(prompt)
        print(Fore.BLUE + "Unity:", answer)

        # optional single critique pass
        critique = self.reflect(answer)
        if "<OK>" not in critique:
            print(Fore.MAGENTA + "Reflection suggestion:", critique)
        return answer


def main():
    api_key = load_api_key()
    llm     = init_llm(api_key)
    retriever = setup_tools(api_key, llm, return_retriever_only=True)
    tools    = setup_tools(api_key, llm, return_retriever_only=False)

    reflection_agent = ReflectionAgent(llm)
    agent = init_agent(llm, tools)

    run_cli(agent, reflection_agent=reflection_agent, fact_sheet_retriever=retriever)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(Fore.RED + f"Fatal error → {e}")
    finally:
        print(Fore.RESET + "Exiting Unity AI.")
        
