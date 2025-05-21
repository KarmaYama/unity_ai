def run_tests(agent):
    queries = [
        "I was arrested by immigration officers and I need help.",
        "How can I renew my asylum seeker permit in Cape Town?",
        "My landlord kicked me out because I’m a refugee.",
        "what are you?"
    ]
    for i, q in enumerate(queries, 1):
        try:
            result = agent.invoke({"input": q})
            print(f"[Test {i}] {q}\n→ {result['output']}\n")
        except Exception as e:
            print(f"[Test {i}] Failed: {e}")