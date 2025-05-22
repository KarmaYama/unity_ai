from core.db import log_case
import json
import time
import random

MAX_RETRIES = 5
GREETINGS = {"hi", "hello", "hey", "hiya", "hola"}

def smart_invoke(agent, user_input):
    retries = 0
    base_delay = 2  # seconds

    while retries < MAX_RETRIES:
        try:
            return agent.invoke({"input": user_input})
        except Exception as e:
            if "429" in str(e):
                delay = base_delay * (2 ** retries) + random.random()
                print(f"Unity: Rate limit hit. Retrying in {round(delay,2)} seconds...")
                time.sleep(delay)
                retries += 1
            else:
                raise
    raise RuntimeError("Too many retries due to rate-limiting. Try again later.")

def run_cli(agent):
    print("Unity: Hello, how can I help you today? Type 'exit' to quit.")
    
    while True:
        user_input = input("You> ").strip()
        low = user_input.lower()

        # 1) Exit
        if low in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe.")
            break

        # 2) Greeting shortcut (avoid calling agent)
        if low in GREETINGS:
            print("Unity: Please tell me about your issue so I can log it in JSON format.")
            print("Example: 'I was stopped by police and they confiscated my ID.'\n")
            continue

        # 3) Call agent
        try:
            response = smart_invoke(agent, user_input)
            raw = response.get("output", "").strip()

            # 4) Try parsing JSON
            try:
                data = json.loads(raw)

                # 4a) Clarification prompt
                if data.get("issue") == "Clarification required":
                    print(f"Unity: {data['next_step']}\n")
                    continue

                # 4b) Valid case → log & show
                issue     = data["issue"]
                severity  = int(data.get("severity", 3))
                next_step = data["next_step"]

                log_case(issue, severity, next_step)
                print("Unity: Case logged successfully:")
                print(f"  • Issue     → {issue}")
                print(f"  • Severity  → {severity}")
                print(f"  • Next Step → {next_step}\n")

            except json.JSONDecodeError:
                # 5) Non-JSON fallback reminder
                print("Unity: I can only respond in JSON format. Please ask me something I can log as a case.\n")
                
        except RuntimeError as e:
            print(f"Unity: {e}\n")
        except Exception as e:
            print(f"Unity: Unexpected error → {e}\n")

        time.sleep(6)
