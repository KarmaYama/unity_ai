from core.db import log_case
import json
import time

def run_cli(agent):
    print("Unity: Hello, how can I help you today? Type 'exit' to quit.")
    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Unity: Goodbye! Stay safe. 👋")
            break
        try:
            response = agent.invoke({"input": user_input})
            raw = response.get("output", "").strip()
            try:
                data = json.loads(raw)
                log_case(data["issue"], int(data["severity"]), data["next_step"])
                print(f"Unity: Issue → {data['issue']} | Severity → {data['severity']} | Next Step → {data['next_step']}\n")
            except json.JSONDecodeError:
                print(f"Unity: {raw}\n")  # Fallback to plain output
        except Exception as e:
            print("Runtime error:", e)
        time.sleep(1)  # Prevent rapid-fire requests
