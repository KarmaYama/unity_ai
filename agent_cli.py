# agent_cli.py

from core.db import log_case
import json
import time
import random
from colorama import Fore

MAX_RETRIES = 5
GREETINGS = {"hi", "hello", "hey", "hiya", "hola"}
FACTSHEET_COMMAND = "talk to factsheet"
BACK_COMMAND = "back"


def smart_invoke(agent, user_input):
    retries, base_delay = 0, 2
    while retries < MAX_RETRIES:
        try:
            print(Fore.YELLOW + f"[DEBUG] smart_invoke sending input: {user_input}")
            return agent.invoke({"input": user_input})
        except Exception as e:
            if "429" in str(e):
                delay = base_delay * (2 ** retries) + random.random()
                print(Fore.RED + f"Unity: Rate limit hit. Retrying in {round(delay,2)}s...")
                time.sleep(delay)
                retries += 1
            else:
                raise
    raise RuntimeError("Too many retries due to rate-limiting. Try again later.")


def run_cli(agent, reflection_agent=None):
    print("Unity: Hello! Ask me anything or type 'exit' to quit.")
    print(f"Type '{FACTSHEET_COMMAND}' to enter fact-sheet mode, or just ask directly for facts.")

    using_factsheet_mode = False

    while True:
        user_input = input("You> ").strip()
        if not user_input:
            continue
        low = user_input.lower()

        # Exit
        if low in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe.")
            break

        # Exit fact-sheet mode
        if low == BACK_COMMAND and using_factsheet_mode:
            using_factsheet_mode = False
            print("Unity: Exited fact-sheet mode. Back to normal operation.")
            continue

        # Enter fact-sheet mode
        if low == FACTSHEET_COMMAND:
            if reflection_agent:
                using_factsheet_mode = True
                print("Unity: Entered fact-sheet mode. Ask me anything from the fact sheet.")
            else:
                print("Unity: Fact-sheet mode is not available.")
            continue

        # If in fact-sheet mode or if user just asks a fact question:
        if using_factsheet_mode or reflection_agent:
            try:
                response = reflection_agent.run(user_input)
                print(Fore.CYAN + f"Unity: {response}\n")
            except Exception as e:
                print(Fore.RED + f"Unity (Fact Sheet): {e}\n")
            continue

        # Fallback to JSON case-logging
        try:
            ai_response = smart_invoke(agent, user_input)
            raw = ai_response.get("output", "").strip()
            try:
                data = json.loads(raw)
                if data.get("issue") == "Clarification required":
                    print(f"Unity: {data['next_step']}\n")
                    continue

                log_case(
                    data["issue"],
                    int(data.get("severity", 3)),
                    data["next_step"]
                )
                print("Unity: Case logged successfully:")
                print(f"  • Issue     → {data['issue']}")
                print(f"  • Severity  → {data.get('severity', 3)}")
                print(f"  • Next Step → {data['next_step']}\n")

            except json.JSONDecodeError:
                print("Unity: I can only respond in JSON format. Please ask me something I can log as a case.\n")

        except RuntimeError as e:
            print(Fore.RED + f"Unity: {e}\n")
        except Exception as e:
            print(Fore.RED + f"Unity: Unexpected error → {e}\n")

        time.sleep(1)
