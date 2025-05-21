from core.db import log_case
import json
import time
import random

MAX_RETRIES = 5

def smart_invoke(agent, user_input):
    retries = 0
    base_delay = 2  # seconds

    while retries < MAX_RETRIES:
        try:
            response = agent.invoke({"input": user_input})
            return response
        except Exception as e:
            if "429" in str(e):
                delay = base_delay * (2 ** retries) + random.uniform(0, 1)
                print(f"Unity: Rate limit hit. Retrying in {round(delay, 2)} seconds...")
                time.sleep(delay)
                retries += 1
            else:
                raise  # Non-rate-limit error, propagate it
    raise RuntimeError("Too many retries due to rate-limiting. Try again later.")


def run_cli(agent):
    print("Unity: Hello, how can I help you today? Type 'exit' to quit.")
    
    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe. 👋")
            break

        try:
            response = smart_invoke(agent, user_input)
            raw = response.get("output", "").strip()

            try:
                data = json.loads(raw)

                if data.get("issue") == "Clarification required":
                    print(f"Unity: 🤖 {data['next_step']}\n")
                    continue

                issue = data.get("issue")
                severity = int(data.get("severity", 3))  # Default fallback
                next_step = data.get("next_step")

                log_case(issue, severity, next_step)
                print(f"Unity: Case logged successfully:\n"
                      f"  • Issue     → {issue}\n"
                      f"  • Severity  → {severity}\n"
                      f"  • Next Step → {next_step}\n")

            except json.JSONDecodeError:
                print(f"Unity: ( JSON parse failed)\n{raw}\n")

        except RuntimeError as e:
            print(f"Unity: {e}")
        except Exception as e:
            print(f"Unity: Unexpected error → {e}")

        time.sleep(1)
        print("Unity: How else can I assist you? (Type 'exit' to quit)")