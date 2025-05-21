import sqlite3

conn = sqlite3.connect("unity_cases.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS cases (
    id         INTEGER PRIMARY KEY,
    issue      TEXT NOT NULL,
    severity   INTEGER NOT NULL,
    next_step  TEXT NOT NULL,
    timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

def log_case(issue: str, severity: int, next_step: str) -> None:
    cursor.execute(
        "INSERT INTO cases (issue, severity, next_step) VALUES (?, ?, ?)",
        (issue, severity, next_step)
    )
    conn.commit()
