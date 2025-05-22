from core.db import log_case
import json
import time
import random

MAX_RETRIES = 5
GREETINGS = {"hi", "hello", "hey", "hiya", "hola"}
FACTSHEET_COMMAND = "talk to factsheet"

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

def run_cli(agent, reflection_agent=None, fact_sheet_retriever=None):
    print("Unity: Hello, how can I help you today? Type 'exit' to quit.")
    print(f"You can also type '{FACTSHEET_COMMAND}' to interact with the fact sheet.")

    using_factsheet_mode = False

    while True:
        user_input = input("You> ").strip()
        low = user_input.lower()

        # 1) Exit
        if low in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe.")
            break

        # 2) Greeting shortcut (avoid calling agent)
        if low in GREETINGS and not using_factsheet_mode:
            print("Unity: Please tell me about your issue so I can log it in JSON format.")
            print("Example: 'I was stopped by police and they confiscated my ID.'\n")
            continue

        # 3) Enter fact sheet interaction mode
        if low == FACTSHEET_COMMAND:
            if reflection_agent and fact_sheet_retriever:
                print("Unity: Entering fact sheet interaction mode. Ask me anything about the content.")
                using_factsheet_mode = True
                continue
            else:
                print("Unity: Fact sheet interaction mode is not set up yet.")
                continue

        # 4) Fact sheet interaction
        if using_factsheet_mode:
            if reflection_agent and fact_sheet_retriever:
                relevant_docs = fact_sheet_retriever.get_relevant_documents(user_input)
                if relevant_docs:
                    context = "\n".join([doc.page_content for doc in relevant_docs])
                    response = reflection_agent.run(user_input, context)
                    print(f"Unity (Fact Sheet): {response}")
                else:
                    print("Unity (Fact Sheet): I couldn't find relevant information in the fact sheet.")
            else:
                print("Unity: Fact sheet interaction mode is not properly initialized.")
            continue

        # 5) Default agent call (for logging cases)
        if not using_factsheet_mode:
            try:
                response = smart_invoke(agent, user_input)
                raw = response.get("output", "").strip()

                # 6) Try parsing JSON
                try:
                    data = json.loads(raw)

                    # 6a) Clarification prompt
                    if data.get("issue") == "Clarification required":
                        print(f"Unity: {data['next_step']}\n")
                        continue

                    # 6b) Valid case -> log & show
                    issue = data["issue"]
                    severity = int(data.get("severity", 3))
                    next_step = data["next_step"]

                    log_case(issue, severity, next_step)
                    print("Unity: Case logged successfully:")
                    print(f"  • Issue     → {issue}")
                    print(f"  • Severity  → {severity}")
                    print(f"  • Next Step → {next_step}\n")

                except json.JSONDecodeError:
                    # 7) Non-JSON fallback reminder
                    print("Unity: I can only respond in JSON format. Please ask me something I can log as a case.\n")

            except RuntimeError as e:
                print(f"Unity: {e}\n")
            except Exception as e:
                print(f"Unity: Unexpected error → {e}\n")

        time.sleep(1) # Reduced sleep time for interaction