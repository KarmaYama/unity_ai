from core.db import log_case
import json
import time
import random
from colorama import Fore

MAX_RETRIES = 5
GREETINGS = {"hi", "hello", "hey", "hiya", "hola"}
FACTSHEET_COMMAND = "talk to factsheet"


def smart_invoke(agent, user_input):
    retries = 0
    base_delay = 2  # seconds

    while retries < MAX_RETRIES:
        try:
            print(Fore.YELLOW + f"[DEBUG] smart_invoke sending input: {user_input}")
            return agent.invoke({"input": user_input})
        except Exception as e:
            # rate-limit backoff
            if "429" in str(e):
                delay = base_delay * (2 ** retries) + random.random()
                print(Fore.RED + f"Unity: Rate limit hit. Retrying in {round(delay,2)} seconds...")
                time.sleep(delay)
                retries += 1
            else:
                raise
    raise RuntimeError("Too many retries due to rate-limiting. Try again later.")


def run_cli(agent, reflection_agent=None, fact_sheet_retriever=None):
    print("Unity: Hello, how can I help you today? Type 'exit' to quit.")
    print(f"You can also type '{FACTSHEET_COMMAND}' to interact with the fact sheet.")

    using_factsheet_mode = False

    while True:
        user_input = input("You> ").strip()
        if not user_input:
            continue  # skip blank lines

        low = user_input.lower()

        # 1) Quit
        if low in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe.")
            break

        # 2) Friendly greeting
        if low in GREETINGS and not using_factsheet_mode:
            print("Unity: Please tell me about your issue so I can log it in JSON format.")
            print("Example: 'I was stopped by police and they confiscated my ID.'\n")
            continue

        # 3) Enter fact-sheet mode
        if low == FACTSHEET_COMMAND:
            if reflection_agent and fact_sheet_retriever:
                print("Unity: Entering fact sheet interaction mode. Ask me anything about the content.")
                using_factsheet_mode = True
            else:
                print("Unity: Fact sheet interaction mode is not set up yet.")
            continue

    # 4) Fact-sheet interaction
    if using_factsheet_mode:
        try:
            summary = fact_sheet_retriever.invoke(user_input)
        except Exception as e:
            print(Fore.RED + f"Unity (Fact Sheet): Retrieval error → {e}")
            return

        # summary is a string, so this check is safe:
        if summary.startswith("I couldn’t find"):
            print(Fore.CYAN + f"Unity (Fact Sheet): {summary}")
        else:
            try:
                response = reflection_agent.run(user_input, summary)
                print(Fore.CYAN + f"Unity (Fact Sheet): {response}")
            except Exception as e:
                print(Fore.RED + f"Unity (Fact Sheet) Unexpected error → {e}")
        # 5) Default (case-logging) flow
        try:
            ai_response = smart_invoke(agent, user_input)
            raw = ai_response.get("output", "").strip()

            try:
                data = json.loads(raw)
                # Clarification branch
                if data.get("issue") == "Clarification required":
                    print(f"Unity: {data['next_step']}\n")
                    return

                # Valid case → log & display
                issue = data["issue"]
                severity = int(data.get("severity", 3))
                next_step = data["next_step"]

                log_case(issue, severity, next_step)
                print("Unity: Case logged successfully:")
                print(f"  • Issue     → {issue}")
                print(f"  • Severity  → {severity}")
                print(f"  • Next Step → {next_step}\n")

            except json.JSONDecodeError:
                print("Unity: I can only respond in JSON format. Please ask me something I can log as a case.\n")

        except RuntimeError as e:
            print(Fore.RED + f"Unity: {e}\n")
        except Exception as e:
            print(Fore.RED + f"Unity: Unexpected error → {e}\n")

        time.sleep(1)  # brief pause before next prompt
