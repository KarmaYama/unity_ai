from core.config import load_api_key, init_llm
from core.tools import setup_tools
from agent_cli import run_cli
from langchain_google_genai import ChatGoogleGenerativeAI
from colorama import Fore

BASE_GENERATION_SYSTEM_PROMPT = """
You will be given context from a fact sheet. Generate a helpful answer to the user's question based on this information.
"""

BASE_REFLECTION_SYSTEM_PROMPT = """
Critique the previous answer to ensure it is accurate, helpful, and directly answers the user's question based on the provided fact sheet context. If the answer is good, say "<OK>". Otherwise, provide specific suggestions for improvement.
"""

class ReflectionAgent:
    def __init__(self, llm: ChatGoogleGenerativeAI, n_reflect_steps=2):
        self.llm = llm
        self.n_reflect_steps = n_reflect_steps

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = self.llm.invoke(messages)
        return response.content

    def reflect(self, system_prompt: str, previous_answer: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": previous_answer},
        ]
        response = self.llm.invoke(messages)
        return response.content

    def run(self, query: str, context: str) -> str:
        generation_prompt = f"{BASE_GENERATION_SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {query}"
        answer = self.generate(BASE_GENERATION_SYSTEM_PROMPT, f"Context:\n{context}\n\nQuestion: {query}")
        print(Fore.BLUE + "\nInitial Answer:", answer)

        for i in range(self.n_reflect_steps):
            reflection_prompt = f"{BASE_REFLECTION_SYSTEM_PROMPT}"
            critique = self.reflect(reflection_prompt, answer)
            print(Fore.GREEN + f"\nCritique ({i+1}):", critique)
            if "<OK>" in critique:
                break
            # For simplicity, we're not re-generating based on critique in this basic prototype
            # In a more advanced version, you would use the critique to refine the prompt and regenerate.

        return answer # Returning the last generated answer for this prototype

def main():
    api_key = load_api_key()
    llm = init_llm(api_key)
    retriever = setup_tools(api_key, llm)
    reflection_agent = ReflectionAgent(llm)

    run_cli(None, reflection_agent=reflection_agent, fact_sheet_retriever=retriever) # Pass agents and retriever

if __name__ == "__main__":
    main()
    print("Unity AI Assistant with Reflection Agent.")